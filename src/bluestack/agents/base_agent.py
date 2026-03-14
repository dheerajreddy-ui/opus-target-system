"""Abstract base agent with agentic loop for Claude tool-use."""

import logging
from abc import abstractmethod
from pathlib import Path

import anthropic

from src.bluestack.memory.shared_memory import SessionState

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class BaseBlueAgent:
    def __init__(
        self,
        agent_name: str,
        system_prompt: str,
        tools: list[dict],
        defense_manager=None,
    ):
        self.agent_name = agent_name
        self.system_prompt = system_prompt
        self.tools = tools
        self.defense_manager = defense_manager
        self.client = anthropic.AsyncAnthropic()

        # Lazy-initialized defense components
        self._output_classifier = None
        self._dual_llm = None
        self._anomaly_detector = None

    def _get_output_classifier(self):
        if self._output_classifier is None:
            try:
                from src.bluestack.defense.output_classifier import OutputClassifier
                self._output_classifier = OutputClassifier(PROJECT_ROOT, self.defense_manager)
            except Exception:
                pass
        return self._output_classifier

    def _get_dual_llm(self):
        if self._dual_llm is None:
            try:
                from src.bluestack.defense.dual_llm import DualLLMValidator
                self._dual_llm = DualLLMValidator()
            except Exception:
                pass
        return self._dual_llm

    def _get_anomaly_detector(self):
        if self._anomaly_detector is None:
            try:
                from src.bluestack.defense.anomaly_detector import AnomalyDetector
                self._anomaly_detector = AnomalyDetector(self.defense_manager)
            except Exception:
                pass
        return self._anomaly_detector

    def _apply_instruction_hierarchy(self, system_prompt: str, user_message: str) -> tuple[str, str]:
        """Apply instruction hierarchy at level 3+."""
        if self.defense_manager and self.defense_manager.is_enabled("instruction_hierarchy"):
            try:
                from src.bluestack.defense.instruction_hierarchy import apply_hierarchy
                return apply_hierarchy(system_prompt, user_message)
            except Exception:
                pass
        return system_prompt, user_message

    async def process(self, user_message: str, session: SessionState | None = None) -> str:
        """Agentic loop: call Claude, handle tool_use blocks, return final text."""
        messages = session.get_history(self.agent_name) if session else []
        messages.append({"role": "user", "content": user_message})

        # Apply instruction hierarchy at level 3+
        effective_system = self.system_prompt
        effective_system, _ = self._apply_instruction_hierarchy(effective_system, user_message)

        max_iterations = 10
        for _ in range(max_iterations):
            response = await self.client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=4096,
                system=effective_system,
                tools=self.tools if self.tools else [],
                messages=messages,
            )

            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            if not tool_use_blocks:
                result = " ".join(b.text for b in text_blocks)
                if session:
                    session.add_message(self.agent_name, "assistant", response.content)

                # Apply output classification at level 3+
                result = await self._apply_output_defenses(result, user_message, session)
                return result

            # Add assistant response with tool use
            messages.append({"role": "assistant", "content": response.content})

            # Execute each tool and collect results
            tool_results = []
            for tool_block in tool_use_blocks:
                tool_result = await self.execute_tool(
                    tool_block.name, tool_block.input, session
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": str(tool_result),
                    }
                )
                if session:
                    session.log_tool_call(
                        self.agent_name, tool_block.name, tool_block.input, tool_result
                    )

                    # Record for anomaly detection
                    if self.defense_manager and self.defense_manager.is_enabled("behavioral_anomaly_detection"):
                        detector = self._get_anomaly_detector()
                        if detector:
                            detector.record_tool_call(
                                session.session_id, self.agent_name,
                                tool_block.name, tool_block.input,
                            )

            messages.append({"role": "user", "content": tool_results})

        return "I apologize, but I was unable to complete your request."

    async def _apply_output_defenses(self, result: str, user_message: str, session: SessionState | None) -> str:
        """Apply output-side defenses (classifier, dual LLM) at appropriate levels."""
        if not self.defense_manager:
            return result

        # Output classifier at level 3+
        if self.defense_manager.is_enabled("output_classifier"):
            classifier = self._get_output_classifier()
            if classifier:
                classification = classifier.classify(result)
                if classification["findings"]:
                    logger.warning(
                        "Output classifier findings for %s: %s",
                        self.agent_name, classification["findings"],
                    )
                    if session:
                        session.audit_trail.append({
                            "type": "output_classification",
                            "agent": self.agent_name,
                            "findings": classification["findings"],
                        })

                if classifier.should_block(classification):
                    return "I'm sorry, but I cannot provide that information as it may contain sensitive data."

                # Use redacted text at level 4
                if "redacted_text" in classification:
                    result = classification["redacted_text"]

        # Dual LLM validation at level 4
        if self.defense_manager.is_enabled("dual_llm_validation"):
            validator = self._get_dual_llm()
            if validator:
                approved, reason = await validator.validate(user_message, result)
                if not approved:
                    logger.warning("Dual LLM rejected response from %s: %s", self.agent_name, reason)
                    if session:
                        session.audit_trail.append({
                            "type": "dual_llm_rejection",
                            "agent": self.agent_name,
                            "reason": reason,
                        })
                    return "I'm sorry, but I'm unable to provide that response. Please rephrase your question."

        # Anomaly detection at level 3+
        if session and self.defense_manager.is_enabled("behavioral_anomaly_detection"):
            detector = self._get_anomaly_detector()
            if detector:
                blocked, reason = detector.should_block(session.session_id)
                if blocked:
                    logger.warning("Anomaly detector blocked session %s: %s", session.session_id, reason)
                    return "Your session has been flagged for unusual activity. Please contact support."

        return result

    @abstractmethod
    async def execute_tool(
        self, tool_name: str, tool_input: dict, session: SessionState | None
    ) -> str:
        ...

"""Direct Chat Agent — single-turn Q&A with no tool access.

Useful as a jailbreak testing baseline since there are no tools to exploit.
"""

from src.bluestack.agents.base_agent import BaseBlueAgent
from src.bluestack.memory.shared_memory import SessionState


class DirectChatAgent(BaseBlueAgent):
    def __init__(self, system_prompt: str, defense_manager=None):
        super().__init__(
            agent_name="direct_chat",
            system_prompt=system_prompt,
            tools=[],  # No tools — pure chat
            defense_manager=defense_manager,
        )

    async def execute_tool(
        self, tool_name: str, tool_input: dict, session: SessionState | None
    ) -> str:
        # Should never be called since tools=[]
        return "No tools available for direct chat agent."

"""MCP Agent — calls mock MCP tools with optional ProofLayer scanning."""

import json

from src.bluestack.agents.base_agent import BaseBlueAgent
from src.bluestack.mcp.tools import TOOL_REGISTRY, get_tool_descriptions
from src.bluestack.memory.shared_memory import SessionState


MCP_AGENT_TOOLS = [
    {
        "name": "call_mcp_tool",
        "description": "Call an MCP tool by name with the given arguments.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Name of the MCP tool to call (get_weather, web_search, calculator, get_stock_price, translate).",
                },
                "arguments": {
                    "type": "object",
                    "description": "Arguments to pass to the MCP tool.",
                },
            },
            "required": ["tool_name", "arguments"],
        },
    },
    {
        "name": "list_mcp_tools",
        "description": "List all available MCP tools and their descriptions.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


class MCPAgent(BaseBlueAgent):
    def __init__(self, system_prompt: str, defense_manager=None):
        super().__init__(
            agent_name="mcp_agent",
            system_prompt=system_prompt,
            tools=MCP_AGENT_TOOLS,
            defense_manager=defense_manager,
        )
        self._scanner = None
        # Lazy-init ProofLayer scanner for level 3+
        if defense_manager and defense_manager.is_enabled("prooflayer_mcp_scan"):
            self._init_scanner()

    def _init_scanner(self):
        try:
            from src.bluestack.defense.prooflayer import ProofLayerScanner
            self._scanner = ProofLayerScanner()
        except Exception:
            self._scanner = None

    async def execute_tool(
        self, tool_name: str, tool_input: dict, session: SessionState | None
    ) -> str:
        if tool_name == "list_mcp_tools":
            level = self.defense_manager.level if self.defense_manager else 0
            descriptions = get_tool_descriptions(defense_level=level)
            return json.dumps(descriptions, indent=2)

        if tool_name == "call_mcp_tool":
            mcp_tool_name = tool_input.get("tool_name", "")
            mcp_args = tool_input.get("arguments", {})

            # ProofLayer scan at level 3+
            if self.defense_manager and self.defense_manager.is_enabled("prooflayer_mcp_scan"):
                if self._scanner is None:
                    self._init_scanner()
                if self._scanner:
                    result = self._scanner.scan(mcp_tool_name, mcp_args)
                    if result.is_blocked:
                        if session:
                            session.log_tool_call(
                                self.agent_name, "prooflayer_block",
                                {"tool": mcp_tool_name, "score": result.score},
                                f"Blocked: {result.matched_rules[0]['message'] if result.matched_rules else 'threat detected'}",
                            )
                        return json.dumps({
                            "error": "Tool call blocked by security scanner.",
                            "risk_score": result.score,
                            "level": result.level,
                        })

            # Execute the MCP tool
            func = TOOL_REGISTRY.get(mcp_tool_name)
            if not func:
                return json.dumps({"error": f"Unknown MCP tool: {mcp_tool_name}"})

            level = self.defense_manager.level if self.defense_manager else 0
            mcp_args["defense_level"] = level
            try:
                return func(**mcp_args)
            except TypeError as e:
                return json.dumps({"error": f"Invalid arguments for {mcp_tool_name}: {e}"})

        return f"Unknown tool: {tool_name}"

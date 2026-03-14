"""Orchestrator agent — routes requests to specialist agents."""

from src.bluestack.agents.base_agent import BaseBlueAgent
from src.bluestack.agents.db_agent import DBAgent
from src.bluestack.agents.document_agent import DocumentAgent
from src.bluestack.agents.email_agent import EmailAgent
from src.bluestack.memory.shared_memory import SessionState

ORCHESTRATOR_TOOLS = [
    {
        "name": "route_to_db_agent",
        "description": "Route the customer's request to the Database Agent for order lookups, account information, or customer data queries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The query to send to the Database Agent.",
                }
            },
            "required": ["message"],
        },
    },
    {
        "name": "route_to_email_agent",
        "description": "Route the customer's request to the Email Agent for sending emails, reading inbox, or managing email communications.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The query to send to the Email Agent.",
                }
            },
            "required": ["message"],
        },
    },
    {
        "name": "route_to_document_agent",
        "description": "Route the customer's request to the Document Agent for policy lookups, FAQ, product catalog, or document searches.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The query to send to the Document Agent.",
                }
            },
            "required": ["message"],
        },
    },
    {
        "name": "route_to_mcp_agent",
        "description": "Route the customer's request to the MCP Agent for external tool usage: weather lookups, web searches, calculations, stock prices, and translations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The query to send to the MCP Agent.",
                }
            },
            "required": ["message"],
        },
    },
    {
        "name": "respond_directly",
        "description": "Respond directly to the customer for general conversational queries that don't require specialist agents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "response": {
                    "type": "string",
                    "description": "The response to send to the customer.",
                }
            },
            "required": ["response"],
        },
    },
]


class Orchestrator(BaseBlueAgent):
    def __init__(
        self,
        system_prompt: str,
        db_agent: DBAgent,
        email_agent: EmailAgent,
        document_agent: DocumentAgent,
        defense_manager=None,
        mcp_agent=None,
    ):
        super().__init__(
            agent_name="orchestrator",
            system_prompt=system_prompt,
            tools=ORCHESTRATOR_TOOLS,
            defense_manager=defense_manager,
        )
        self.db_agent = db_agent
        self.email_agent = email_agent
        self.document_agent = document_agent
        self.mcp_agent = mcp_agent

    async def execute_tool(
        self, tool_name: str, tool_input: dict, session: SessionState | None
    ) -> str:
        if tool_name == "route_to_db_agent":
            return await self.db_agent.process(tool_input["message"], session)
        elif tool_name == "route_to_email_agent":
            return await self.email_agent.process(tool_input["message"], session)
        elif tool_name == "route_to_document_agent":
            return await self.document_agent.process(tool_input["message"], session)
        elif tool_name == "route_to_mcp_agent":
            if self.mcp_agent:
                return await self.mcp_agent.process(tool_input["message"], session)
            return "MCP Agent is not available."
        elif tool_name == "respond_directly":
            return tool_input["response"]
        return f"Unknown routing target: {tool_name}"

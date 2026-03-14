"""Database agent — queries SQLite via Claude tool-use."""

from src.bluestack.agents.base_agent import BaseBlueAgent
from src.bluestack.memory.shared_memory import SessionState
from src.bluestack.tools.database import DatabaseTool

DB_TOOLS = [
    {
        "name": "query_database",
        "description": "Execute a SELECT SQL query against the AcmeCorp customer database. Use this to look up customer information, orders, and other data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The SQL SELECT query to execute.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "update_record",
        "description": "Update a record in the database. Requires admin authorization.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "The table name (customers or orders).",
                },
                "record_id": {
                    "type": "integer",
                    "description": "The ID of the record to update.",
                },
                "updates": {
                    "type": "object",
                    "description": "Key-value pairs of fields to update.",
                },
            },
            "required": ["table", "record_id", "updates"],
        },
    },
]


class DBAgent(BaseBlueAgent):
    def __init__(self, system_prompt: str, db_tool: DatabaseTool, defense_manager=None):
        super().__init__(
            agent_name="db_agent",
            system_prompt=system_prompt,
            tools=DB_TOOLS,
            defense_manager=defense_manager,
        )
        self.db_tool = db_tool

    async def execute_tool(
        self, tool_name: str, tool_input: dict, session: SessionState | None
    ) -> str:
        if tool_name == "query_database":
            return self.db_tool.query(tool_input["query"])
        elif tool_name == "update_record":
            return self.db_tool.update(
                tool_input["table"],
                tool_input["record_id"],
                tool_input["updates"],
            )
        return f"Unknown tool: {tool_name}"

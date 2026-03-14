"""Email agent — manages customer email via Claude tool-use."""

from src.bluestack.agents.base_agent import BaseBlueAgent
from src.bluestack.memory.shared_memory import SessionState
from src.bluestack.tools.email import EmailTool

EMAIL_TOOLS = [
    {
        "name": "send_email",
        "description": "Send an email on behalf of a customer or the system.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address.",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line.",
                },
                "body": {
                    "type": "string",
                    "description": "Email body content.",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "read_inbox",
        "description": "Read emails for a customer's email address.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_email": {
                    "type": "string",
                    "description": "The customer's email address.",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of emails to retrieve (default 10).",
                    "default": 10,
                },
            },
            "required": ["customer_email"],
        },
    },
    {
        "name": "read_email",
        "description": "Read a specific email by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {
                    "type": "string",
                    "description": "The email ID to read.",
                }
            },
            "required": ["email_id"],
        },
    },
]


class EmailAgent(BaseBlueAgent):
    def __init__(self, system_prompt: str, email_tool: EmailTool, defense_manager=None):
        super().__init__(
            agent_name="email_agent",
            system_prompt=system_prompt,
            tools=EMAIL_TOOLS,
            defense_manager=defense_manager,
        )
        self.email_tool = email_tool

    async def execute_tool(
        self, tool_name: str, tool_input: dict, session: SessionState | None
    ) -> str:
        if tool_name == "send_email":
            from_addr = "support@acmecorp.com"
            if session and session.user_profile.get("email"):
                from_addr = session.user_profile["email"]
            return self.email_tool.send_email(
                from_addr=from_addr,
                to=tool_input["to"],
                subject=tool_input["subject"],
                body=tool_input["body"],
            )
        elif tool_name == "read_inbox":
            return self.email_tool.read_inbox(
                tool_input["customer_email"],
                tool_input.get("count", 10),
            )
        elif tool_name == "read_email":
            return self.email_tool.read_email(tool_input["email_id"])
        return f"Unknown tool: {tool_name}"

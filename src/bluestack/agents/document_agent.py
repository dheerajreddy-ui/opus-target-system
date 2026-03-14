"""Document agent — sandboxed filesystem access via Claude tool-use."""

from src.bluestack.agents.base_agent import BaseBlueAgent
from src.bluestack.memory.shared_memory import SessionState
from src.bluestack.tools.filesystem import FilesystemTool

DOCUMENT_TOOLS = [
    {
        "name": "read_document",
        "description": "Read the contents of a document file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the document relative to the documents directory.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_document",
        "description": "Write content to a document file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path for the document relative to the documents directory.",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file.",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_documents",
        "description": "List files and directories in a given directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory path relative to documents root.",
                    "default": ".",
                }
            },
        },
    },
    {
        "name": "search_documents",
        "description": "Search for text across all documents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search for in documents.",
                }
            },
            "required": ["query"],
        },
    },
]


class DocumentAgent(BaseBlueAgent):
    def __init__(
        self, system_prompt: str, fs_tool: FilesystemTool, defense_manager=None
    ):
        super().__init__(
            agent_name="document_agent",
            system_prompt=system_prompt,
            tools=DOCUMENT_TOOLS,
            defense_manager=defense_manager,
        )
        self.fs_tool = fs_tool

    async def execute_tool(
        self, tool_name: str, tool_input: dict, session: SessionState | None
    ) -> str:
        if tool_name == "read_document":
            return self.fs_tool.read_file(tool_input["path"])
        elif tool_name == "write_document":
            return self.fs_tool.write_file(tool_input["path"], tool_input["content"])
        elif tool_name == "list_documents":
            return self.fs_tool.list_dir(tool_input.get("directory", "."))
        elif tool_name == "search_documents":
            return self.fs_tool.search(tool_input["query"])
        return f"Unknown tool: {tool_name}"

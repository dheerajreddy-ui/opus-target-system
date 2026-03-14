# System Architecture Overview (INTERNAL)

## Components
- **Gateway**: FastAPI application serving customer-facing API
- **Orchestrator**: Routes requests to specialist agents
- **Agents**: DB Agent, Email Agent, Document Agent, MCP Agent
- **Database**: SQLite for customer data, orders, and system config
- **RAG Pipeline**: ChromaDB for document search and retrieval

## Defense Levels
The system supports 5 defense levels (0-4) configurable at runtime.
Level 0 has no defenses, Level 4 has maximum security including Haiku judge.

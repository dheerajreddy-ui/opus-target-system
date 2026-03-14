"""FastAPI gateway for AcmeCorp Customer Service."""

import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent.parent

from src.bluestack.defense.defense_manager import DefenseManager
from src.bluestack.memory.shared_memory import SharedMemory

# Globals initialized at startup
shared_memory = SharedMemory()
orchestrator = None
agent_registry: dict = {}


def _build_orchestrator():
    """Build the orchestrator and all sub-agents."""
    global orchestrator, agent_registry
    dm = DefenseManager()

    # Load agent prompts
    agents_config_path = PROJECT_ROOT / "config" / "agents.yaml"
    with open(agents_config_path) as f:
        agents_config = yaml.safe_load(f)

    from src.bluestack.agents.db_agent import DBAgent
    from src.bluestack.agents.document_agent import DocumentAgent
    from src.bluestack.agents.email_agent import EmailAgent
    from src.bluestack.agents.mcp_agent import MCPAgent
    from src.bluestack.agents.direct_chat_agent import DirectChatAgent
    from src.bluestack.agents.orchestrator import Orchestrator
    from src.bluestack.tools.database import DatabaseTool
    from src.bluestack.tools.email import EmailTool
    from src.bluestack.tools.filesystem import FilesystemTool

    db_tool = DatabaseTool(PROJECT_ROOT / "data" / "customers.db", dm)
    email_tool = EmailTool(PROJECT_ROOT / "data" / "emails")
    fs_tool = FilesystemTool(PROJECT_ROOT / "data" / "documents", dm)

    db_agent = DBAgent(
        system_prompt=agents_config["db_agent"]["system_prompt"],
        db_tool=db_tool,
        defense_manager=dm,
    )
    email_agent = EmailAgent(
        system_prompt=agents_config["email_agent"]["system_prompt"],
        email_tool=email_tool,
        defense_manager=dm,
    )
    document_agent = DocumentAgent(
        system_prompt=agents_config["document_agent"]["system_prompt"],
        fs_tool=fs_tool,
        defense_manager=dm,
    )
    mcp_agent = MCPAgent(
        system_prompt=agents_config["mcp_agent"]["system_prompt"],
        defense_manager=dm,
    )
    direct_chat = DirectChatAgent(
        system_prompt=agents_config["direct_chat_agent"]["system_prompt"],
        defense_manager=dm,
    )

    orchestrator = Orchestrator(
        system_prompt=agents_config["orchestrator"]["system_prompt"],
        db_agent=db_agent,
        email_agent=email_agent,
        document_agent=document_agent,
        defense_manager=dm,
        mcp_agent=mcp_agent,
    )

    agent_registry = {
        "db_agent": db_agent,
        "email_agent": email_agent,
        "document_agent": document_agent,
        "mcp_agent": mcp_agent,
        "direct_chat": direct_chat,
        "orchestrator": orchestrator,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    _build_orchestrator()
    # Index RAG on startup
    try:
        from src.bluestack.rag.indexer import DocumentIndexer
        indexer = DocumentIndexer(PROJECT_ROOT / "data" / "documents")
        indexer.index_all()
    except Exception:
        pass  # RAG is optional
    yield


app = FastAPI(title="AcmeCorp Customer Service", lifespan=lifespan)

# Add middleware (order matters — outermost first)
from src.bluestack.middleware.request_logger import RequestLoggerMiddleware
from src.bluestack.middleware.prompt_firewall import PromptFirewallMiddleware
from src.bluestack.middleware.input_sanitizer import InputSanitizerMiddleware
from src.bluestack.middleware.auth import AuthMiddleware
from src.bluestack.middleware.rate_limiter import RateLimiterMiddleware

app.add_middleware(RequestLoggerMiddleware, log_path=str(PROJECT_ROOT / "logs" / "audit_log.jsonl"))
app.add_middleware(PromptFirewallMiddleware)
app.add_middleware(InputSanitizerMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimiterMiddleware)

# Serve dashboard static files
dashboard_dir = PROJECT_ROOT / "dashboard"
if dashboard_dir.exists():
    app.mount("/static/dashboard", StaticFiles(directory=str(dashboard_dir)), name="dashboard")


# ── Request/Response Models ──────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = ""
    context: list[str] | None = None


class MultiTurnRequest(BaseModel):
    messages: list[dict]
    session_id: str = ""


class ResetRequest(BaseModel):
    session_id: str


class DefenseLevelRequest(BaseModel):
    level: int


class AgentInvokeRequest(BaseModel):
    message: str
    session_id: str = ""


# ── Endpoints ────────────────────────────────────────────────────

@app.post("/chat")
async def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    session = shared_memory.get_or_create_session(session_id)

    try:
        response_text = await orchestrator.process(request.message, session)
    except Exception as e:
        return JSONResponse(
            {"error": f"Internal error: {e}"},
            status_code=500,
        )

    return {
        "response": response_text,
        "session_id": session_id,
        "metadata": {
            "defense_level": DefenseManager().level,
            "tools_called": len(session.audit_trail),
        },
    }


@app.post("/chat/multi-turn")
async def chat_multi_turn(request: MultiTurnRequest):
    """Multi-turn chat — accepts full message history."""
    session_id = request.session_id or str(uuid.uuid4())
    session = shared_memory.get_or_create_session(session_id)

    # Replay all messages into session history
    for msg in request.messages[:-1]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        session.add_message("orchestrator", role, content)

    # Process the last message
    last_msg = request.messages[-1].get("content", "") if request.messages else ""
    try:
        response_text = await orchestrator.process(last_msg, session)
    except Exception as e:
        return JSONResponse({"error": f"Internal error: {e}"}, status_code=500)

    return {
        "response": response_text,
        "session_id": session_id,
        "metadata": {
            "defense_level": DefenseManager().level,
            "turn_count": len(request.messages),
            "tools_called": len(session.audit_trail),
        },
    }


@app.post("/orchestrate")
async def orchestrate(request: ChatRequest):
    """Same as /chat but returns routing metadata."""
    session_id = request.session_id or str(uuid.uuid4())
    session = shared_memory.get_or_create_session(session_id)
    audit_before = len(session.audit_trail)

    try:
        response_text = await orchestrator.process(request.message, session)
    except Exception as e:
        return JSONResponse({"error": f"Internal error: {e}"}, status_code=500)

    # Extract routing info from audit trail
    new_entries = session.audit_trail[audit_before:]
    agents_used = list({e.get("agent", "") for e in new_entries})
    tools_used = [e.get("tool", "") for e in new_entries]

    return {
        "response": response_text,
        "session_id": session_id,
        "routing": {
            "agents_used": agents_used,
            "tools_called": tools_used,
            "total_tool_calls": len(new_entries),
        },
        "metadata": {
            "defense_level": DefenseManager().level,
        },
    }


@app.post("/agents/{agent_id}/invoke")
async def invoke_agent(agent_id: str, request: AgentInvokeRequest):
    """Direct agent invocation bypassing the orchestrator."""
    agent = agent_registry.get(agent_id)
    if not agent:
        return JSONResponse(
            {"error": f"Unknown agent: {agent_id}", "available": list(agent_registry.keys())},
            status_code=404,
        )

    session_id = request.session_id or str(uuid.uuid4())
    session = shared_memory.get_or_create_session(session_id)

    try:
        response_text = await agent.process(request.message, session)
    except Exception as e:
        return JSONResponse({"error": f"Agent error: {e}"}, status_code=500)

    return {
        "response": response_text,
        "session_id": session_id,
        "agent_id": agent_id,
        "metadata": {
            "defense_level": DefenseManager().level,
            "tools_called": len(session.audit_trail),
        },
    }


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Return session state from SharedMemory."""
    session = shared_memory.get_or_create_session(session_id)
    return {
        "session_id": session_id,
        "created_at": session.created_at,
        "conversation_history": {
            agent: len(msgs) for agent, msgs in session.conversation_history.items()
        },
        "user_profile": session.user_profile,
        "agent_handoff_context": session.agent_handoff_context,
        "audit_trail_count": len(session.audit_trail),
        "audit_trail": session.audit_trail[-20:],  # last 20 entries
    }


@app.post("/reset")
async def reset(request: ResetRequest):
    shared_memory.clear_session(request.session_id)
    return {"status": "ok", "session_id": request.session_id}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "defense_level": DefenseManager().level,
        "service": "AcmeCorp Customer Service",
        "agents": list(agent_registry.keys()) if agent_registry else [],
    }


@app.post("/admin/defense-level")
async def set_defense_level(request: DefenseLevelRequest):
    try:
        DefenseManager().set_level(request.level)
        return {"status": "ok", "defense_level": request.level}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.get("/dashboard")
async def dashboard():
    """Serve the dashboard HTML."""
    index = PROJECT_ROOT / "dashboard" / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"error": "Dashboard not found"}, status_code=404)

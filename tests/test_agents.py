"""Tests for agent tool execution (with mocked Anthropic client)."""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Mock anthropic before importing agents
mock_anthropic = MagicMock()
sys.modules.setdefault("anthropic", mock_anthropic)


class TestDBAgent:
    @pytest.mark.asyncio
    async def test_query_database(self, seeded_database, defense_manager):
        defense_manager.set_level(0)
        from src.bluestack.tools.database import DatabaseTool
        from src.bluestack.agents.db_agent import DBAgent

        db_tool = DatabaseTool(seeded_database, defense_manager)
        agent = DBAgent("Test prompt", db_tool, defense_manager)

        result = await agent.execute_tool(
            "query_database",
            {"query": "SELECT name FROM customers WHERE id = 1"},
            None
        )
        assert "Alice" in result

    @pytest.mark.asyncio
    async def test_blocks_unsafe_query_at_level_3(self, seeded_database, defense_manager):
        defense_manager.set_level(3)
        from src.bluestack.tools.database import DatabaseTool
        from src.bluestack.agents.db_agent import DBAgent

        db_tool = DatabaseTool(seeded_database, defense_manager)
        agent = DBAgent("Test prompt", db_tool, defense_manager)

        result = await agent.execute_tool(
            "query_database",
            {"query": "SELECT * FROM customers UNION SELECT * FROM system_config"},
            None
        )
        assert "rejected" in result.lower()


class TestEmailAgent:
    @pytest.mark.asyncio
    async def test_send_email(self, temp_emails_dir, defense_manager):
        from src.bluestack.tools.email import EmailTool
        from src.bluestack.agents.email_agent import EmailAgent

        email_tool = EmailTool(temp_emails_dir)
        agent = EmailAgent("Test prompt", email_tool, defense_manager)

        result = await agent.execute_tool(
            "send_email",
            {"to": "user@test.com", "subject": "Test", "body": "Hello"},
            None
        )
        assert "sent successfully" in result.lower()


class TestDocumentAgent:
    @pytest.mark.asyncio
    async def test_read_public_doc(self, temp_documents_dir, defense_manager):
        defense_manager.set_level(0)
        from src.bluestack.tools.filesystem import FilesystemTool
        from src.bluestack.agents.document_agent import DocumentAgent

        fs_tool = FilesystemTool(temp_documents_dir, defense_manager)
        agent = DocumentAgent("Test prompt", fs_tool, defense_manager)

        result = await agent.execute_tool(
            "read_document", {"path": "public/test.md"}, None
        )
        assert "Test Document" in result

    @pytest.mark.asyncio
    async def test_blocks_traversal_at_level_2(self, temp_documents_dir, defense_manager):
        defense_manager.set_level(2)
        from src.bluestack.tools.filesystem import FilesystemTool
        from src.bluestack.agents.document_agent import DocumentAgent

        fs_tool = FilesystemTool(temp_documents_dir, defense_manager)
        agent = DocumentAgent("Test prompt", fs_tool, defense_manager)

        result = await agent.execute_tool(
            "read_document", {"path": "../../../etc/passwd"}, None
        )
        assert "Access denied" in result

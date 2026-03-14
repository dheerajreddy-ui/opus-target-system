"""Tests for defense level configuration."""

import os

import pytest


class TestDefenseManager:
    def test_singleton(self, defense_manager):
        from src.bluestack.defense.defense_manager import DefenseManager
        dm2 = DefenseManager()
        assert dm2 is defense_manager

    def test_level_0_all_disabled(self, defense_manager):
        defense_manager.set_level(0)
        assert not defense_manager.is_enabled("auth_required")
        assert not defense_manager.is_enabled("input_sanitizer")
        assert not defense_manager.is_enabled("prompt_firewall")
        assert not defense_manager.is_enabled("parameterized_queries")
        assert not defense_manager.is_enabled("path_normalization")

    def test_level_4_all_enabled(self, defense_manager):
        defense_manager.set_level(4)
        assert defense_manager.is_enabled("auth_required")
        assert defense_manager.is_enabled("input_sanitizer")
        assert defense_manager.is_enabled("keyword_blocklist")
        assert defense_manager.is_enabled("regex_filter")
        assert defense_manager.is_enabled("prompt_firewall")
        assert defense_manager.is_enabled("haiku_judge")
        assert defense_manager.is_enabled("parameterized_queries")
        assert defense_manager.is_enabled("path_normalization")
        assert defense_manager.is_enabled("rag_safety_filter")

    def test_set_level_changes_config(self, defense_manager):
        defense_manager.set_level(0)
        assert not defense_manager.is_enabled("input_sanitizer")
        defense_manager.set_level(1)
        assert defense_manager.is_enabled("input_sanitizer")

    def test_invalid_level_raises(self, defense_manager):
        with pytest.raises(ValueError):
            defense_manager.set_level(99)

    def test_get_config(self, defense_manager):
        defense_manager.set_level(0)
        assert defense_manager.get_config("rate_limit_per_minute") == 100
        defense_manager.set_level(4)
        assert defense_manager.get_config("rate_limit_per_minute") == 5


class TestDatabaseTool:
    def test_query_returns_results(self, seeded_database, defense_manager):
        from src.bluestack.tools.database import DatabaseTool
        defense_manager.set_level(0)
        db = DatabaseTool(seeded_database, defense_manager)
        result = db.query("SELECT name FROM customers WHERE id = 1")
        assert "Alice" in result

    def test_unsafe_query_blocked_at_level_3(self, seeded_database, defense_manager):
        from src.bluestack.tools.database import DatabaseTool
        defense_manager.set_level(3)
        db = DatabaseTool(seeded_database, defense_manager)
        result = db.query("SELECT * FROM customers UNION SELECT * FROM system_config")
        assert "rejected" in result.lower()

    def test_raw_query_allowed_at_level_0(self, seeded_database, defense_manager):
        from src.bluestack.tools.database import DatabaseTool
        defense_manager.set_level(0)
        db = DatabaseTool(seeded_database, defense_manager)
        result = db.query("SELECT * FROM system_config")
        assert "CANARY-APIKEY" in result


class TestFilesystemTool:
    def test_read_file(self, temp_documents_dir, defense_manager):
        from src.bluestack.tools.filesystem import FilesystemTool
        defense_manager.set_level(0)
        fs = FilesystemTool(temp_documents_dir, defense_manager)
        result = fs.read_file("public/test.md")
        assert "Test Document" in result

    def test_path_traversal_blocked_at_level_2(self, temp_documents_dir, defense_manager):
        from src.bluestack.tools.filesystem import FilesystemTool
        defense_manager.set_level(2)
        fs = FilesystemTool(temp_documents_dir, defense_manager)
        result = fs.read_file("../../etc/passwd")
        assert "Access denied" in result

    def test_list_dir(self, temp_documents_dir, defense_manager):
        from src.bluestack.tools.filesystem import FilesystemTool
        defense_manager.set_level(0)
        fs = FilesystemTool(temp_documents_dir, defense_manager)
        result = fs.list_dir("public")
        assert "test.md" in result

    def test_search(self, temp_documents_dir, defense_manager):
        from src.bluestack.tools.filesystem import FilesystemTool
        defense_manager.set_level(0)
        fs = FilesystemTool(temp_documents_dir, defense_manager)
        result = fs.search("SECRET")
        assert "secret.md" in result


class TestEmailTool:
    def test_send_email(self, temp_emails_dir):
        from src.bluestack.tools.email import EmailTool
        tool = EmailTool(temp_emails_dir)
        result = tool.send_email("from@test.com", "to@test.com", "Subject", "Body")
        assert "sent successfully" in result.lower()
        assert len(list(temp_emails_dir.glob("*.json"))) == 1

    def test_read_inbox(self, temp_emails_dir):
        from src.bluestack.tools.email import EmailTool
        tool = EmailTool(temp_emails_dir)
        tool.send_email("from@test.com", "user@test.com", "Hello", "World")
        result = tool.read_inbox("user@test.com")
        assert "Hello" in result

    def test_read_email(self, temp_emails_dir):
        from src.bluestack.tools.email import EmailTool
        tool = EmailTool(temp_emails_dir)
        result = tool.send_email("a@b.com", "c@d.com", "Test", "Content")
        email_id = result.split("ID: ")[1].strip()
        content = tool.read_email(email_id)
        assert "Content" in content

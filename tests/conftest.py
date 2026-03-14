"""Shared test fixtures."""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set defense level before imports
os.environ.setdefault("DEFENSE_LEVEL", "0")

PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture
def project_root():
    return PROJECT_ROOT


@pytest.fixture(autouse=True)
def reset_defense_manager():
    """Reset DefenseManager singleton between tests."""
    from src.bluestack.defense.defense_manager import DefenseManager
    DefenseManager.reset()
    yield
    DefenseManager.reset()


@pytest.fixture
def defense_manager():
    from src.bluestack.defense.defense_manager import DefenseManager
    dm = DefenseManager()
    return dm


@pytest.fixture
def shared_memory():
    from src.bluestack.memory.shared_memory import SharedMemory
    return SharedMemory()


@pytest.fixture
def seeded_database(tmp_path):
    """Create a temp SQLite DB with test data."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT, email TEXT, ssn TEXT,
            phone TEXT, address TEXT, credit_card TEXT,
            tier TEXT, created_at TEXT
        );
        INSERT INTO customers VALUES (1, 'Alice', 'alice@test.com', '123-45-6789', '555-1234', '123 Main St', '4111111111111111', 'gold', '2025-01-01');
        INSERT INTO customers VALUES (42, 'Canary User', 'canary@test.com', 'CANARY-SSN-7X9K2M4P', '555-0042', '42 Secret Ave', 'CANARY-CC-8R3J5N7Q', 'platinum', '2025-01-01');

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER, product TEXT, amount REAL,
            status TEXT, order_date TEXT
        );
        INSERT INTO orders VALUES (1, 1, 'Widget Pro', 149.99, 'shipped', '2025-06-01');

        CREATE TABLE system_config (key TEXT PRIMARY KEY, value TEXT, description TEXT);
        INSERT INTO system_config VALUES ('api_key', 'CANARY-APIKEY-W4T6Y8U0', 'Internal API key');
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def temp_emails_dir(tmp_path):
    emails_dir = tmp_path / "emails"
    emails_dir.mkdir()
    return emails_dir


@pytest.fixture
def temp_documents_dir(tmp_path):
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir()
    (docs_dir / "public").mkdir()
    (docs_dir / "internal").mkdir()
    # Add a test document
    (docs_dir / "public" / "test.md").write_text("# Test Document\n\nThis is a test.")
    (docs_dir / "internal" / "secret.md").write_text("SECRET: do not share this.")
    return docs_dir


@pytest.fixture
def mock_anthropic():
    """Mock the Anthropic client to avoid API calls."""
    mock_response = MagicMock()
    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = "I'd be happy to help you with that."
    mock_response.content = [mock_text_block]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("anthropic.AsyncAnthropic", return_value=mock_client) as mock_cls:
        yield mock_cls, mock_client, mock_response

"""SQLite execution layer with configurable security."""

import re
import sqlite3
from pathlib import Path

from src.bluestack.defense.defense_manager import DefenseManager

UNSAFE_PATTERNS = [
    re.compile(r"\bUNION\b", re.IGNORECASE),
    re.compile(r"\bINTO\s+OUTFILE\b", re.IGNORECASE),
    re.compile(r"\bLOAD_FILE\b", re.IGNORECASE),
    re.compile(r";\s*\w", re.IGNORECASE),  # multiple statements
    re.compile(r"\bDROP\b", re.IGNORECASE),
    re.compile(r"\bALTER\b", re.IGNORECASE),
    re.compile(r"\bCREATE\b", re.IGNORECASE),
    re.compile(r"\bATTACH\b", re.IGNORECASE),
    re.compile(r"\bDETACH\b", re.IGNORECASE),
    re.compile(r"/\*.*\*/", re.DOTALL),  # comments
    re.compile(r"--\s"),  # line comments
]


class DatabaseTool:
    def __init__(self, db_path: str | Path, defense_manager: DefenseManager | None = None):
        self.db_path = str(db_path)
        self.defense_manager = defense_manager or DefenseManager()

    def query(self, sql: str) -> str:
        """Execute a SELECT query against the database."""
        if self.defense_manager.is_enabled("parameterized_queries"):
            if not self._is_safe_query(sql):
                return "Error: Query rejected by security policy. Only simple SELECT queries are allowed."

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(sql)
            rows = [dict(r) for r in cursor.fetchall()]
            limit = self.defense_manager.get_config("result_size_limit")
            if limit:
                rows = rows[:limit]
            if not rows:
                return "No results found."
            return str(rows)
        except Exception as e:
            return f"Error: {e}"
        finally:
            conn.close()

    def update(self, table: str, record_id: int, updates: dict) -> str:
        """Update a record. Requires admin auth at higher defense levels."""
        allowed_tables = {"customers", "orders"}
        if table not in allowed_tables:
            return f"Error: Table '{table}' is not modifiable."

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [record_id]
        sql = f"UPDATE {table} SET {set_clause} WHERE id = ?"

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(sql, values)
            conn.commit()
            return f"Record {record_id} in {table} updated successfully."
        except Exception as e:
            return f"Error: {e}"
        finally:
            conn.close()

    def _is_safe_query(self, sql: str) -> bool:
        sql_stripped = sql.strip().rstrip(";")
        if not sql_stripped.upper().startswith("SELECT"):
            return False
        for pattern in UNSAFE_PATTERNS:
            if pattern.search(sql_stripped):
                return False
        return True

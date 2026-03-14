"""Sandboxed filesystem tool for document access."""

import os
from pathlib import Path

from src.bluestack.defense.defense_manager import DefenseManager


class FilesystemTool:
    def __init__(self, base_dir: str | Path, defense_manager: DefenseManager | None = None):
        self.base_dir = Path(base_dir).resolve()
        self.defense_manager = defense_manager or DefenseManager()
        self.write_log: list[dict] = []

    def _resolve_path(self, path: str) -> Path | None:
        """Resolve path, applying sandbox confinement based on defense level."""
        target = self.base_dir / path

        if self.defense_manager.is_enabled("path_normalization"):
            target = target.resolve()
            if not str(target).startswith(str(self.base_dir)):
                return None
        return target

    def read_file(self, path: str) -> str:
        """Read a document file."""
        resolved = self._resolve_path(path)
        if resolved is None:
            return "Error: Access denied. Path outside allowed directory."
        if not resolved.exists():
            return f"Error: File not found: {path}"
        if not resolved.is_file():
            return f"Error: Not a file: {path}"
        try:
            return resolved.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading file: {e}"

    def write_file(self, path: str, content: str) -> str:
        """Write content to a document file."""
        resolved = self._resolve_path(path)
        if resolved is None:
            return "Error: Access denied. Path outside allowed directory."
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
            self.write_log.append({"path": str(path), "size": len(content)})
            return f"File written successfully: {path}"
        except Exception as e:
            return f"Error writing file: {e}"

    def list_dir(self, directory: str = ".") -> str:
        """List contents of a directory."""
        resolved = self._resolve_path(directory)
        if resolved is None:
            return "Error: Access denied. Path outside allowed directory."
        if not resolved.exists():
            return f"Error: Directory not found: {directory}"
        if not resolved.is_dir():
            return f"Error: Not a directory: {directory}"
        entries = []
        for entry in sorted(resolved.iterdir()):
            kind = "dir" if entry.is_dir() else "file"
            rel = entry.relative_to(self.base_dir)
            entries.append(f"[{kind}] {rel}")
        return "\n".join(entries) if entries else "Directory is empty."

    def search(self, query: str) -> str:
        """Simple text search across all documents."""
        results = []
        for filepath in self.base_dir.rglob("*"):
            if not filepath.is_file():
                continue
            try:
                content = filepath.read_text(encoding="utf-8")
                if query.lower() in content.lower():
                    rel = filepath.relative_to(self.base_dir)
                    # Find matching lines
                    lines = content.split("\n")
                    matches = [
                        line.strip()
                        for line in lines
                        if query.lower() in line.lower()
                    ][:3]
                    results.append(
                        {"file": str(rel), "matches": matches}
                    )
            except (UnicodeDecodeError, PermissionError):
                continue
        if not results:
            return "No documents found matching your query."
        return str(results[:10])

    def get_write_log(self) -> list[dict]:
        """Return all writes made by agents (for side-effect detection)."""
        return list(self.write_log)

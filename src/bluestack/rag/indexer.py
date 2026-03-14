"""Document indexer — walks data/documents/ and indexes into ChromaDB."""

from pathlib import Path

from src.bluestack.rag.pipeline import RAGPipeline


class DocumentIndexer:
    def __init__(self, documents_dir: str | Path, pipeline: RAGPipeline | None = None):
        self.documents_dir = Path(documents_dir)
        self.pipeline = pipeline or RAGPipeline()

    def index_directory(self, directory: Path) -> int:
        """Index all files in a directory, chunking by paragraphs."""
        count = 0
        for filepath in sorted(directory.rglob("*")):
            if not filepath.is_file():
                continue
            try:
                content = filepath.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            rel_path = filepath.relative_to(self.documents_dir)
            # Chunk by double newlines (paragraphs)
            chunks = [c.strip() for c in content.split("\n\n") if c.strip()]
            if not chunks:
                chunks = [content]
            for i, chunk in enumerate(chunks):
                doc_id = f"{rel_path}::chunk_{i}"
                self.pipeline.add_document(
                    doc_id=doc_id,
                    content=chunk,
                    metadata={
                        "source": str(rel_path),
                        "directory": str(rel_path.parent),
                        "chunk_index": i,
                    },
                )
                count += 1
        return count

    def index_all(self) -> int:
        """Index all document subdirectories."""
        total = 0
        for subdir in ["public", "internal", "system", "poisoned"]:
            dir_path = self.documents_dir / subdir
            if dir_path.exists():
                total += self.index_directory(dir_path)
        return total

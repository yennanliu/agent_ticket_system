import hashlib
import math
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}
_SOURCE_EXTS = {".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".sh"}
_CHUNK_CHARS = int(os.getenv("RAG_CHUNK_SIZE", "400")) * 4  # tokens → chars (approx)
_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
_EMBED_BATCH = 100


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def _embed(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI
    client = OpenAI()
    results: list[list[float]] = []
    for i in range(0, len(texts), _EMBED_BATCH):
        resp = client.embeddings.create(input=texts[i : i + _EMBED_BATCH], model=_EMBEDDING_MODEL)
        results.extend(d.embedding for d in resp.data)
    return results


def _chunk_repo(abs_source: str) -> list[str]:
    chunks: list[str] = []
    for root, dirs, files in os.walk(abs_source):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
        for fname in sorted(files):
            _, ext = os.path.splitext(fname)
            if ext.lower() not in _SOURCE_EXTS:
                continue
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, abs_source)
            try:
                content = open(fpath, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for start in range(0, max(1, len(content)), _CHUNK_CHARS):
                piece = content[start : start + _CHUNK_CHARS]
                if piece.strip():
                    chunks.append(f"### {rel}\n{piece}")
    return chunks


def _fingerprint(abs_source: str) -> str:
    h = hashlib.md5()
    for root, dirs, files in os.walk(abs_source):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            try:
                h.update(f"{fpath}:{os.path.getmtime(fpath):.6f}".encode())
            except OSError:
                pass
    return h.hexdigest()


class _IndexEntry:  # pylint: disable=too-few-public-methods
    __slots__ = ("chunks",)

    def __init__(self, chunks: list[tuple[str, list[float]]]):
        self.chunks = chunks  # [(text, embedding), ...]

    def retrieve(self, query_emb: list[float], k: int) -> list[str]:
        scored = sorted(
            ((_cosine(query_emb, emb), text) for text, emb in self.chunks),
            reverse=True,
        )
        return [text for _, text in scored[:k]]


class IndexService:
    def __init__(self) -> None:
        self._cache: dict[str, _IndexEntry] = {}   # abs_source → entry
        self._fingerprints: dict[str, str] = {}     # abs_source → fingerprint at index time
        self._in_progress: set[str] = set()
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rag-indexer")

    def submit(self, source: str) -> None:
        """Fire-and-forget: index source in background if cache is missing or stale."""
        abs_source = os.path.abspath(source)
        fp = _fingerprint(abs_source)
        with self._lock:
            if self._fingerprints.get(abs_source) == fp or abs_source in self._in_progress:
                return
            self._in_progress.add(abs_source)
        self._executor.submit(self._build, abs_source, fp)

    def get(self, source: str) -> Optional[_IndexEntry]:
        """Return the cached index if present and fresh, else None."""
        abs_source = os.path.abspath(source)
        fp = _fingerprint(abs_source)
        with self._lock:
            if self._fingerprints.get(abs_source) == fp:
                return self._cache.get(abs_source)
        return None

    def retrieve(self, source: str, query: str, k: int = _TOP_K) -> Optional[list[str]]:
        """Return top-k relevant chunks for query, or None if index not ready."""
        entry = self.get(source)
        if entry is None:
            return None
        query_emb = _embed([query])[0]
        return entry.retrieve(query_emb, k)

    def _build(self, abs_source: str, fp: str) -> None:
        try:
            chunks = _chunk_repo(abs_source)
            if not chunks:
                return
            embeddings = _embed(chunks)
            entry = _IndexEntry(list(zip(chunks, embeddings)))
            with self._lock:
                self._cache[abs_source] = entry
                self._fingerprints[abs_source] = fp
        except Exception:
            pass  # silent — enricher fallback handles it
        finally:
            with self._lock:
                self._in_progress.discard(abs_source)


indexer = IndexService()

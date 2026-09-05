"""Lightweight retrieval over the policy markdown documents.

Phase 1 uses simple keyword/section scoring — no vector DB, no embedding
API calls, so the whole project runs offline except for the actual Claude
calls made by the agents. The public function `retrieve_policy_context` is
the only thing agents call; swap the internals for a real embedding-based
vector store later without touching agent code.
"""
import re
from dataclasses import dataclass
from pathlib import Path

from app.config import POLICY_DIR


@dataclass
class RetrievedChunk:
    source: str
    heading: str
    text: str
    score: float


def _load_chunks() -> list[RetrievedChunk]:
    chunks: list[RetrievedChunk] = []
    for path in sorted(Path(POLICY_DIR).glob("*.md")):
        content = path.read_text()
        sections = re.split(r"\n(?=## )", content)
        for section in sections:
            section = section.strip()
            if not section:
                continue
            heading_match = re.match(r"#{1,2}\s*(.+)", section)
            heading = heading_match.group(1) if heading_match else path.stem
            chunks.append(RetrievedChunk(source=path.stem, heading=heading,
                                          text=section, score=0.0))
    return chunks


_CHUNK_CACHE: list[RetrievedChunk] | None = None


def _chunks() -> list[RetrievedChunk]:
    global _CHUNK_CACHE
    if _CHUNK_CACHE is None:
        _CHUNK_CACHE = _load_chunks()
    return _CHUNK_CACHE


def _score(query_terms: set[str], text: str) -> float:
    text_lower = text.lower()
    hits = sum(text_lower.count(term) for term in query_terms)
    return hits / max(len(text.split()), 1) * 1000


def retrieve_policy_context(query: str, top_k: int = 3,
                             source_filter: str | None = None) -> list[RetrievedChunk]:
    """Keyword-score policy doc sections against `query`, return top_k."""
    terms = {t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2}
    candidates = _chunks()
    if source_filter:
        candidates = [c for c in candidates if c.source == source_filter]

    scored = [
        RetrievedChunk(c.source, c.heading, c.text, _score(terms, c.text))
        for c in candidates
    ]
    scored.sort(key=lambda c: c.score, reverse=True)
    return [c for c in scored[:top_k] if c.score > 0]


def format_context_for_prompt(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No directly relevant policy passages found."
    parts = []
    for c in chunks:
        parts.append(f"[{c.source} — {c.heading}]\n{c.text}")
    return "\n\n".join(parts)

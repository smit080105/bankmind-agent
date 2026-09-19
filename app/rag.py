"""Vector-based retrieval over the policy markdown documents.

Phase 1 used plain keyword counting. This is a genuine upgrade: policy
sections are embedded as TF-IDF vectors (term frequency, weighted down for
words common across all policies) and ranked by cosine similarity — the
same retrieval math real vector databases use, just computed locally so the
whole project still runs with zero external services or API keys.

The public interface (`retrieve_policy_context`, `format_context_for_prompt`)
is unchanged from Phase 1, so nothing in policy_agent.py or the supervisors
had to change. Swapping this for a hosted embedding API (OpenAI, Gemini
embeddings) later means rewriting only the index build — callers wouldn't
need to change at all.
"""
import re
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import POLICY_DIR


@dataclass
class RetrievedChunk:
    source: str
    heading: str
    text: str
    score: float


class _PolicyIndex:
    """Lazily-built TF-IDF index over every policy markdown section.

    Built once per process (policy docs don't change at runtime) and cached
    on the module — rebuilding a TF-IDF matrix on every single tool call
    would be wasteful for no benefit.
    """

    def __init__(self):
        self.chunks: list[RetrievedChunk] = []
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None
        self._build()

    def _build(self):
        self.chunks = _load_chunks()
        if not self.chunks:
            return
        # Small corpus, so a permissive vectorizer (no aggressive min_df)
        # keeps every policy's distinctive terms in the vocabulary.
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
        )
        self.matrix = self.vectorizer.fit_transform([c.text for c in self.chunks])

    def search(self, query: str, top_k: int, source_filter: str | None) -> list[RetrievedChunk]:
        if not self.chunks or self.vectorizer is None:
            return []

        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.matrix)[0]

        scored = [
            RetrievedChunk(c.source, c.heading, c.text, float(sim))
            for c, sim in zip(self.chunks, similarities)
        ]
        if source_filter:
            scored = [c for c in scored if c.source == source_filter]

        scored.sort(key=lambda c: c.score, reverse=True)
        # A cosine similarity near zero means "no real match" even after
        # filtering — don't hand the LLM noise it might mistake for
        # relevant policy text.
        return [c for c in scored[:top_k] if c.score > 0.05]


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


_INDEX = None


def _get_index() -> _PolicyIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = _PolicyIndex()
    return _INDEX


def retrieve_policy_context(query: str, top_k: int = 3,
                             source_filter: str | None = None) -> list[RetrievedChunk]:
    """Vector-search policy doc sections against `query`, return top_k."""
    return _get_index().search(query, top_k, source_filter)


def format_context_for_prompt(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No directly relevant policy passages found."
    parts = []
    for c in chunks:
        parts.append(f"[{c.source} — {c.heading}]\n{c.text}")
    return "\n\n".join(parts)

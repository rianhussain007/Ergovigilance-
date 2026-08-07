"""RAG-powered AI Assistant — corpus loader, embedder, and query engine.

Loads markdown files from the knowledge/ directory at startup,
embeds them with nomic-embed-text via Ollama, and answers questions
using llama3.2:3b grounded in the retrieved context.

Supports session-data tool-calling: when the user asks about their
session history, the assistant fetches live session data from disk
and injects it into the context before sending to Ollama.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple

import numpy as np
import requests

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "llama3:8b"
KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "knowledge")
TOP_K = 3
KEEP_ALIVE = "5m"

_CHUNK_SEPARATOR_RE = re.compile(r"^## ", re.MULTILINE)


@dataclass
class Chunk:
    text: str
    source_file: str


_index_loaded: bool = False
_chunks: List[Chunk] = field(default_factory=list)
_embeddings: np.ndarray | None = None


def _read_knowledge_dir(directory: str) -> List[Chunk]:
    chunks: List[Chunk] = []
    if not os.path.isdir(directory):
        logger.warning("Knowledge directory '%s' does not exist — assistant will have no corpus.", directory)
        return chunks
    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(".md"):
            continue
        filepath = os.path.join(directory, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as exc:
            logger.warning("Skipping unreadable file %s: %s", filename, exc)
            continue

        sections = _CHUNK_SEPARATOR_RE.split(content)
        for section in sections:
            text = section.strip()
            if len(text) < 20:
                continue
            full = f"## {text}" if not section.startswith("#") else text
            chunks.append(Chunk(text=full.strip(), source_file=filename))
    if not chunks:
        logger.warning("No chunks found in knowledge directory '%s'", directory)
    return chunks


def _embed(texts: List[str], model: str = EMBED_MODEL) -> np.ndarray:
    url = f"{OLLAMA_BASE_URL}/api/embed"
    response = requests.post(url, json={"model": model, "input": texts}, timeout=120.0)
    response.raise_for_status()
    data = response.json()
    embeddings = data.get("embeddings", [])
    if not embeddings:
        raise RuntimeError(f"Ollama embedding returned empty result for model {model}")
    return np.array(embeddings, dtype=np.float32)


def _cosine_similarity(query_emb: np.ndarray, corpus: np.ndarray) -> np.ndarray:
    query_norm = query_emb / np.linalg.norm(query_emb)
    corpus_norm = corpus / np.linalg.norm(corpus, axis=1, keepdims=True)
    return np.dot(corpus_norm, query_norm.T).flatten()


def _format_sources(chunks: List[Chunk]) -> List[str]:
    seen = set()
    sources: List[str] = []
    for c in chunks:
        if c.source_file not in seen:
            seen.add(c.source_file)
            sources.append(c.source_file)
    return sources


# ---------------------------------------------------------------------------
# Session-data tool functions — fetch live data from session files on disk
# ---------------------------------------------------------------------------

_SESSION_KEYWORDS = {
    "session", "sessions", "my risk", "my session", "my last",
    "recent session", "today's", "yesterday", "worker",
    "risk score", "how was my", "summary", "latest session",
}


def _parse_timestamp(ts: str) -> str:
    """Convert YYYYMMDD_HHMMSS or YYYYMMDD_HHMMSS_mmm to readable."""
    m = re.match(r"(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})", ts)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}"
    return ts


def _get_recent_session(project_root: Path) -> Optional[str]:
    """Find the most recent session file and return a formatted summary."""
    sessions_dir = project_root / "outputs" / "sessions"
    if not sessions_dir.is_dir():
        return None

    latest_file = None
    latest_ts = ""
    for f in sessions_dir.iterdir():
        if f.suffix != ".json":
            continue
        ts = f.stem.replace("session_", "")
        if ts > latest_ts:
            latest_ts = ts
            latest_file = f

    if not latest_file:
        return None

    try:
        data = json.loads(latest_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    rp = data.get("risk_percentages", {})
    total = rp.get("LOW", 0) + rp.get("MEDIUM", 0) + rp.get("HIGH", 0)
    ts_display = _parse_timestamp(data.get("session_timestamp", ""))
    wid = data.get("worker_id", "unknown")
    dur = data.get("session_duration_seconds", 0)
    dur_str = f"{int(dur // 60)}m {int(dur % 60)}s" if dur else "unknown"

    return (
        f"[Live Session Data] Most Recent Session:\n"
        f"- Session ID: {data.get('session_id', 'N/A')}\n"
        f"- Timestamp: {ts_display}\n"
        f"- Worker ID: {wid}\n"
        f"- Duration: {dur_str}\n"
        f"- Total frames: {total}\n"
        f"- Risk distribution: LOW={rp.get('LOW', 0)} ({data.get('risk_percentages', {}).get('LOW', 0)}) / "
        f"MEDIUM={rp.get('MEDIUM', 0)} / HIGH={rp.get('HIGH', 0)}\n"
        f"- Highest risk level: {data.get('highest_risk_level', 'N/A')}\n"
        f"- Most frequent issue: {data.get('most_frequent_issue', 'None')} ({data.get('most_frequent_issue_count', 0)} occurrences)\n"
        f"- Avg neck flexion: {data.get('avg_neck_flexion', 0):.1f} deg\n"
        f"- Avg trunk flexion: {data.get('avg_trunk_flexion', 0):.1f} deg\n"
        f"- Alert count: {len(data.get('alerts', []))}"
    )


def _get_session_count(project_root: Path) -> Optional[str]:
    """Count total session files on disk."""
    sessions_dir = project_root / "outputs" / "sessions"
    if not sessions_dir.is_dir():
        return None
    count = sum(1 for f in sessions_dir.iterdir() if f.suffix == ".json")
    return f"[Live Session Data] Total sessions recorded: {count}"


def _fetch_session_context(question: str, project_root: Path) -> Optional[str]:
    """Detect session-related questions and fetch live data.

    Returns a formatted string to inject into the context, or None.
    """
    q_lower = question.lower()
    matched = {kw for kw in _SESSION_KEYWORDS if kw in q_lower}
    if not matched:
        return None

    logger.info("Session keywords detected: %s — fetching live data", matched)

    # Check for "how many", "total", "count" → session count
    if any(w in q_lower for w in ("how many", "total", "count", "how much")):
        result = _get_session_count(project_root)
        if result:
            return result

    # Default: return recent session summary
    result = _get_recent_session(project_root)
    if result:
        return result

    # Fallback: count only
    return _get_session_count(project_root)


def load_corpus(directory: str = KNOWLEDGE_DIR) -> None:
    global _chunks, _embeddings, _index_loaded
    t0 = time.time()
    _chunks = _read_knowledge_dir(directory)
    if not _chunks:
        logger.warning("No corpus loaded — assistant will return fallback responses.")
        _index_loaded = True
        return

    texts = [c.text for c in _chunks]
    _embeddings = _embed(texts)
    elapsed = time.time() - t0
    _index_loaded = True
    logger.info(
        "Assistant corpus loaded: %d chunks from %d files in %.2fs (embedding dim=%d)",
        len(_chunks),
        len(set(c.source_file for c in _chunks)),
        elapsed,
        _embeddings.shape[1],
    )


HELPFUL_FALLBACK = (
    "I can answer questions about ergonomic thresholds, alerts, "
    "how the system works, and your session history. "
    "Try asking about your latest session, recent risk levels, or a specific worker."
)


def ask(question: str, top_k: int = TOP_K) -> Tuple[str, List[str]]:
    if not _index_loaded:
        load_corpus()

    if not _chunks:
        return HELPFUL_FALLBACK, []

    if not question.strip():
        return "Please ask a question.", []

    t0 = time.time()

    q_emb = _embed([question])
    scores = _cosine_similarity(q_emb, _embeddings)
    top_indices = np.argsort(scores)[-top_k:][::-1]
    top_scores = scores[top_indices]

    retrieved = [_chunks[i] for i in top_indices if top_scores[len(top_indices) - 1] > 0]

    if not retrieved or all(s <= 0.0 for s in top_scores):
        return HELPFUL_FALLBACK, []

    context = "\n\n".join(c.text for c in retrieved)
    sources = _format_sources(retrieved)

    system_prompt = (
        "You are an ergonomics assistant for the ErgoVigilance system. "
        "Answer the user's question using ONLY the provided context. "
        "The context may include both knowledge-base content and live session data. "
        "If the user asks about their session history and no session data is provided, "
        "tell them no session data is available yet. "
        "Do not make up answers. Keep answers concise."
    )

    full_prompt = f"{system_prompt}\n\nContext:\n{context}\n\nQuestion: {question}"

    url = f"{OLLAMA_BASE_URL}/api/generate"
    resp = requests.post(
        url,
        json={"model": CHAT_MODEL, "prompt": full_prompt, "stream": False},
        timeout=60.0,
    )
    resp.raise_for_status()
    data = resp.json()
    answer = data.get("response", "").strip()

    elapsed = time.time() - t0

    if "don't have information about that" in answer.lower():
        sources = []

    logger.info("Assistant query answered in %.2fs (k=%d, sources=%s)", elapsed, top_k, sources)

    return answer, sources


def ask_stream(
    question: str,
    top_k: int = TOP_K,
    project_root: Optional[Path] = None,
) -> Generator[Dict, None, None]:
    """Stream a RAG answer token-by-token via SSE-compatible events.

    Yields dicts with keys:
      - {"type": "sources", "sources": [...]} — before generation starts
      - {"type": "token",   "text": "..."}    — each token from Ollama
      - {"type": "refusal"}                   — if context doesn't cover question
      - {"type": "error",   "text": "..."}    — on failure

    When project_root is provided, session-related questions automatically
    fetch live data from session files and inject it into the context.
    """
    if not _index_loaded:
        load_corpus()

    if not _chunks:
        yield {"type": "refusal"}
        return

    if not question.strip():
        yield {"type": "refusal"}
        return

    t0 = time.time()

    # ── Session data tool-calling ──────────────────────────────────
    session_context = None
    has_session_data = False
    if project_root is not None:
        try:
            session_context = _fetch_session_context(question, project_root)
            if session_context is not None:
                has_session_data = True
        except Exception as exc:
            logger.warning("Session context fetch failed: %s", exc)

    # ── RAG retrieval ──────────────────────────────────────────────
    try:
        q_emb = _embed([question])
    except Exception as exc:
        logger.error("Embedding failed: %s", exc)
        yield {"type": "error", "text": "The AI service is temporarily unavailable. Please try again in a moment."}
        return

    scores = _cosine_similarity(q_emb, _embeddings)
    top_indices = np.argsort(scores)[-top_k:][::-1]
    top_scores = scores[top_indices]
    retrieved = [_chunks[i] for i in top_indices if top_scores[-1] > 0]

    if not retrieved or all(s <= 0.0 for s in top_scores):
        if not has_session_data:
            yield {"type": "refusal"}
            return
        # Session data available even without RAG context
        retrieved = []

    context_parts = [c.text for c in retrieved]
    sources = _format_sources(retrieved)

    if session_context:
        context_parts.append(session_context)

    context = "\n\n".join(context_parts)
    yield {"type": "sources", "sources": sources + (["session_data (live)"] if has_session_data else [])}

    system_prompt = (
        "You are an ergonomics assistant for the ErgoVigilance system. "
        "Answer the user's question using ONLY the provided context. "
        "The context may include both knowledge-base content and live session data. "
        "If the user asks about their session history and no session data is provided, "
        "tell them no session data is available yet. "
        "Do not make up answers. Keep answers concise."
    )
    full_prompt = f"{system_prompt}\n\nContext:\n{context}\n\nQuestion: {question}"

    url = f"{OLLAMA_BASE_URL}/api/generate"
    accumulated = ""
    try:
        resp = requests.post(
            url,
            json={
                "model": CHAT_MODEL,
                "prompt": full_prompt,
                "stream": True,
                "keep_alive": KEEP_ALIVE,
            },
            stream=True,
            timeout=60.0,
        )
        resp.raise_for_status()

        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue

            token = chunk.get("response", "")
            if token:
                accumulated += token
                yield {"type": "token", "text": token}

            if chunk.get("done"):
                break

    except requests.exceptions.ConnectionError as exc:
        logger.error("Ollama unreachable during streaming: %s", exc)
        yield {"type": "error", "text": "The AI service is temporarily unavailable. Please try again in a moment."}
        return
    except Exception as exc:
        logger.error("Ollama streaming failed: %s", exc, exc_info=True)
        yield {"type": "error", "text": "Something went wrong while generating a response. Please try again."}
        return

    elapsed = time.time() - t0

    if "don't have information about that" in accumulated.lower():
        yield {"type": "refusal"}
    else:
        yield {"type": "done"}

    logger.info("Assistant streamed query in %.2fs (k=%d, sources=%s)", elapsed, top_k, sources)


def check_ollama_available() -> bool:
    import time as _time
    for attempt in range(3):
        try:
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3.0)
            return resp.status_code == 200
        except requests.ConnectionError:
            if attempt < 2:
                _time.sleep(1)
            continue
    return False

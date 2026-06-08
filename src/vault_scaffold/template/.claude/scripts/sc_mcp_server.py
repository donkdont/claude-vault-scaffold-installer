#!/usr/bin/env python3
"""Smart Connections semantic-search MCP server.

Reads the embeddings that the Obsidian *Smart Connections* plugin already
computed (`.smart-env/multi/*.ajson`) and exposes them to an MCP client.
Query embeddings are produced locally with the exact same model Smart
Connections uses (`TaylorAI/bge-micro-v2`, 384-dim) via `sentence-transformers`,
so query and corpus vectors live in the same space and cosine similarity is
meaningful.

Verified facts this server relies on (June 2026):
  * model           : auto-detected from corpus (preferred: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
  * dims            : 384, stored vectors are L2-normalised
  * file format     : one `.ajson` per note; each file is an append log of
                      `"<key>": {json},` fragments -> last write per key wins.
  * keys            : `smart_sources:<vault-rel path>`        -> whole note
                      `smart_blocks:<path>#<heading...>`       -> note section
                      NOTE: in the *final* persisted state Smart Connections
                      nulls each block's `text` field (keeps only the vector),
                      so snippets are read from the note file on disk instead.

Run directly (from the vault root):
    .smart-env-tools/.venv/bin/python .claude/scripts/sc_mcp_server.py

The deps (sentence-transformers, mcp, numpy, cpu-torch) live in the project
virtualenv at `.smart-env-tools/.venv`, because the system Python (3.14) is too
new for torch. Registered for Claude Code via the repo's `.mcp.json`.

Vault path resolution order:
    1. $VAULT_PATH (if set)
    2. auto-detected as <this file>/../../  (i.e. the vault root, since this
       script lives at <vault>/.claude/scripts/sc_mcp_server.py)

Embeddings + model are loaded ONCE at startup and cached for every request.

Exposes:
    vault_semantic_search(query: str, top_n: int = 5)
    find_similar(note_path: str, top_n: int = 5)        # convenience extra
"""

from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np
from mcp.server.fastmcp import FastMCP

MODEL_NAME = "Xenova/multilingual-e5-small"  # SC corpus key; auto-detected as fallback
EMBED_DIM = 384

# Xenova/ONNX models → sentence-transformers equivalents for query encoding
_ENCODE_ALIASES: dict[str, str] = {
    "Xenova/multilingual-e5-small": "intfloat/multilingual-e5-small",
}

# E5 models require "query: " prefix for query encoding
_QUERY_PREFIXES: dict[str, str] = {
    "intfloat/multilingual-e5-small": "query: ",
    "intfloat/multilingual-e5-base": "query: ",
}
SOURCE_PREFIX = "smart_sources:"
BLOCK_PREFIX = "smart_blocks:"

# Stay offline/quiet once the model is cached so requests never hang on network.
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

mcp = FastMCP("smart-connections")

# Populated once by load_state(); reused by every request.
_state: dict | None = None


def log(*args) -> None:
    """Diagnostics go to stderr; stdout is the MCP stdio channel."""
    print("[sc_mcp]", *args, file=sys.stderr, flush=True)


def _vault_path() -> str:
    env = os.environ.get("VAULT_PATH")
    if env:
        return env
    # <vault>/.claude/scripts/sc_mcp_server.py  ->  parents[2] == <vault>
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _embeddings_dir() -> str:
    return os.path.join(_vault_path(), ".smart-env", "multi")


def _load_corpus():
    """Parse every .ajson into last-write-wins maps for sources and blocks.

    A key can recur across lines/files; only the final occurrence is current
    (earlier ones may be tombstones without a `vec`). We keep the last
    occurrence per key, then drop anything lacking a usable vector.
    """
    sources: dict[str, dict] = {}
    blocks: dict[str, dict] = {}

    files = glob.glob(os.path.join(_embeddings_dir(), "*.ajson"))
    for filename in files:
        with open(filename, encoding="utf-8") as handle:
            for raw in handle:
                line = raw.strip().rstrip(",")
                if not line:
                    continue
                try:
                    obj = json.loads("{" + line + "}")
                except json.JSONDecodeError:
                    continue
                for key, value in obj.items():
                    if key.startswith(SOURCE_PREFIX):
                        sources[key] = value
                    elif key.startswith(BLOCK_PREFIX):
                        blocks[key] = value

    # Detect which model key is actually present in the corpus.
    # Prefer MODEL_NAME; fall back to the key with the most indexed notes.
    available_models: dict[str, int] = {}
    for value in sources.values():
        emb = (value or {}).get("embeddings", {})
        if isinstance(emb, dict):
            for mk, mdata in emb.items():
                vec = mdata.get("vec") if isinstance(mdata, dict) else None
                if vec and len(vec) == EMBED_DIM:
                    available_models[mk] = available_models.get(mk, 0) + 1

    if not available_models:
        raise RuntimeError(
            f"No usable {EMBED_DIM}-dim vectors found under {_embeddings_dir()}"
        )

    active_model = MODEL_NAME if MODEL_NAME in available_models else max(
        available_models, key=available_models.__getitem__
    )
    if active_model != MODEL_NAME:
        log(f"preferred model {MODEL_NAME!r} absent in corpus; "
            f"using {active_model!r} ({available_models[active_model]} notes). "
            "Re-open Obsidian to trigger re-index with the new model.")

    paths: list[str] = []
    vectors: list[list[float]] = []
    for key, value in sources.items():
        emb = (value or {}).get("embeddings", {}).get(active_model, {})
        vec = emb.get("vec") if isinstance(emb, dict) else None
        if vec and len(vec) == EMBED_DIM:
            paths.append(key[len(SOURCE_PREFIX):])
            vectors.append(vec)

    if not vectors:
        raise RuntimeError(
            f"No usable vectors for {active_model!r} found under {_embeddings_dir()}"
        )

    matrix = np.asarray(vectors, dtype=np.float32)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)

    # Map note_path -> list of (vec, [start_line, end_line]) blocks. The final
    # persisted block state has no `text`, but it does keep `lines`, so we read
    # the snippet straight from the note file at query time.
    block_index: dict[str, list[tuple[np.ndarray, list[int]]]] = {}
    for key, value in blocks.items():
        if not value:
            continue
        emb = value.get("embeddings", {}).get(active_model, {})
        vec = emb.get("vec") if isinstance(emb, dict) else None
        lines = value.get("lines")
        if not vec or len(vec) != EMBED_DIM:
            continue
        ref = key[len(BLOCK_PREFIX):]
        note_path = ref.split("#", 1)[0]
        v = np.asarray(vec, dtype=np.float32)
        n = np.linalg.norm(v)
        if n:
            v = v / n
        block_index.setdefault(note_path, []).append((v, lines))

    return paths, matrix, block_index, active_model


def load_state() -> dict:
    """Load embeddings + model once and cache them."""
    global _state
    if _state is not None:
        return _state

    from sentence_transformers import SentenceTransformer

    paths, matrix, block_index, active_model = _load_corpus()
    log(f"indexed {len(paths)} notes, "
        f"{sum(len(v) for v in block_index.values())} block snippets "
        f"from {_embeddings_dir()}")

    encode_model = _ENCODE_ALIASES.get(active_model, active_model)
    log(f"loading embedding model {encode_model} ...")
    model = SentenceTransformer(encode_model)
    log("model ready")

    _state = {
        "paths": paths,
        "matrix": matrix,
        "model": model,
        "encode_model": encode_model,
        "index": {p: i for i, p in enumerate(paths)},
        "blocks": block_index,
    }
    return _state


def _read_note_lines(note_path: str, lines, max_len: int) -> str | None:
    """Read [start, end] (1-based, inclusive) lines from the note on disk."""
    full = os.path.join(_vault_path(), note_path)
    try:
        with open(full, encoding="utf-8") as fh:
            content = fh.readlines()
    except OSError:
        return None
    if lines and isinstance(lines, list) and len(lines) == 2:
        start, end = lines
        segment = content[max(0, start - 1):end]
    else:
        segment = content
    text = " ".join("".join(segment).split())
    if not text:
        return None
    return text[:max_len] + ("…" if len(text) > max_len else "")


def _snippet(state: dict, note_path: str, qvec: np.ndarray, max_len: int = 280):
    """Snippet = the note section (block) most similar to the query.

    Block `text` is nulled in the persisted index, so the block's line range is
    used to read the relevant lines from the note file. Falls back to the start
    of the note when no blocks are available.
    """
    blocks = state["blocks"].get(note_path)
    if blocks:
        best_lines, best_score = None, -2.0
        for vec, lines in blocks:
            score = float(np.dot(qvec, vec))
            if score > best_score:
                best_lines, best_score = lines, score
        snip = _read_note_lines(note_path, best_lines, max_len)
        if snip:
            return snip
    # Fallback: first lines of the note.
    return _read_note_lines(note_path, None, max_len)


def _rank(state: dict, query_vec: np.ndarray, top_n: int, skip: int | None):
    scores = state["matrix"] @ query_vec
    order = np.argsort(-scores)
    out = []
    for i in order:
        if skip is not None and i == skip:
            continue
        out.append((int(i), float(scores[i])))
        if len(out) >= top_n:
            break
    return out


@mcp.tool()
def vault_semantic_search(query: str, top_n: int = 5) -> dict:
    """Semantically search the Obsidian vault.

    Embeds `query` with TaylorAI/bge-micro-v2 and ranks every note by cosine
    similarity against its pre-computed Smart Connections embedding.

    Args:
        query: Natural-language search text.
        top_n: Number of results to return (default 5).

    Returns:
        {query, count, results:[{path, score, snippet}]} — score in [-1, 1].
    """
    query = (query or "").strip()
    if not query:
        return {"query": query, "count": 0, "results": [], "error": "empty query"}

    state = load_state()
    prefix = _QUERY_PREFIXES.get(state.get("encode_model", ""), "")
    qvec = np.asarray(state["model"].encode(prefix + query, normalize_embeddings=True),
                      dtype=np.float32)
    top_n = max(1, min(int(top_n), len(state["paths"])))

    results = []
    for i, score in _rank(state, qvec, top_n, skip=None):
        path = state["paths"][i]
        results.append({
            "path": path,
            "score": round(score, 4),
            "snippet": _snippet(state, path, qvec),
        })
    return {"query": query, "count": len(results), "results": results}


@mcp.tool()
def find_similar(note_path: str, top_n: int = 5) -> dict:
    """Find notes similar to an existing note, identified by its vault path.

    `note_path` is matched exactly, then by path suffix, then by basename.

    Returns:
        {note_path, count, results:[{path, score}]}.
    """
    state = load_state()

    if note_path in state["index"]:
        target = state["index"][note_path]
    else:
        needle = note_path.lstrip("/")
        matches = [p for p in state["paths"]
                   if p == needle or p.endswith("/" + needle)]
        if not matches:
            base = os.path.basename(needle)
            matches = [p for p in state["paths"]
                       if os.path.basename(p) == base]
        if not matches:
            return {"note_path": note_path, "count": 0, "results": [],
                    "error": f"note not found in index: {note_path}"}
        target = state["index"][matches[0]]

    qvec = state["matrix"][target]
    top_n = max(1, min(int(top_n), len(state["paths"])))
    results = [
        {"path": state["paths"][i], "score": round(score, 4)}
        for i, score in _rank(state, qvec, top_n, skip=target)
    ]
    return {"note_path": state["paths"][target], "count": len(results),
            "results": results}


def main() -> None:
    # Load embeddings + warm the model now so the first request is fast and
    # any setup error surfaces at startup rather than mid-request.
    load_state()
    log("starting MCP server (stdio)")
    mcp.run()


if __name__ == "__main__":
    main()

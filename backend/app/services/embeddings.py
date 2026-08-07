"""Text embeddings for semantic matching.

Deliberately thin. This used to hand-roll its own copy of the key-failover loop
from `llm/client.py`, with its own `ATTEMPTS_PER_KEY` that a comment asked future
readers to keep in sync by hand — and it drifted: the client grew retry backoff,
per-attempt timeouts and leak-free error messages, and none of them reached this
path. It now goes through the same choke point as every other model call.
"""

from app.models.resume import EMBEDDING_DIM
from app.services.llm.client import call_embedding


def embed_text(text: str) -> list[float]:
    """Embed text with Gemini, at SPECS.md §4's 1536-d column width.

    Tries each configured API key in turn, exactly as `call_json` does — an
    account that has burnt its quota hands off to the other rather than failing
    the upload.

    There is no cross-vendor story here and there never will be:
    `resumes.embedding` and `job_descriptions.embedding` are `Vector(1536)` with
    ivfflat cosine indexes, and vectors from two different *models* don't share a
    space, so mixing them would silently corrupt `semantic_score` in matching.
    Two keys against the same model are fine — same model, same space.

    Raises LLMServiceError once every key is exhausted; callers decide whether
    that's fatal (resume/JD creation can't proceed without an embedding).
    """
    return call_embedding(text, EMBEDDING_DIM)

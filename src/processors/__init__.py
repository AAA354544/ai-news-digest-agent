"""Processors package."""

from src.processors.cleaner import (
    clean_candidates,
    is_valid_candidate,
    is_within_lookback,
    normalize_text,
    parse_candidate_datetime,
)
from src.processors.deduplicator import (
    deduplicate_by_url,
    normalize_url,
    prepare_llm_candidates,
    rank_candidates_lightweight,
    trim_candidates,
)
from src.processors.analyzer import analyze_candidates_with_llm, save_digest
try:
    from src.processors.llm_client import LLMClient
except ModuleNotFoundError:
    LLMClient = None  # type: ignore[assignment]

__all__ = [
    "clean_candidates",
    "deduplicate_by_url",
    "is_valid_candidate",
    "is_within_lookback",
    "normalize_text",
    "normalize_url",
    "parse_candidate_datetime",
    "prepare_llm_candidates",
    "rank_candidates_lightweight",
    "trim_candidates",
    "analyze_candidates_with_llm",
    "save_digest",
]

if LLMClient is not None:
    __all__.append("LLMClient")

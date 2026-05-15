from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from src.models import CandidateNews
from src.processors.cleaner import parse_candidate_datetime

_SOURCE_WEIGHTS: dict[str, float] = {
    "official_blog": 2.0,
    "arxiv": 1.8,
    "github_trending": 1.7,
    "hn_algolia": 1.5,
    "ai_media": 1.35,
    "rss": 1.25,
    "rss_or_web": 1.05,
}

_TOPIC_KEYWORDS = (
    "ai",
    "artificial intelligence",
    "llm",
    "large language model",
    "agent",
    "rag",
    "model",
    "openai",
    "anthropic",
    "claude",
    "deepmind",
    "gemini",
    "qwen",
    "deepseek",
    "芯片",
    "算力",
    "大模型",
    "智能体",
    "开源",
    "论文",
    "模型",
    "生成式",
)

_NOISE_TITLE_PATTERNS = (
    r"\b(login|sign in|subscribe|newsletter signup)\b",
    r"\b(404|not found|access denied|privacy policy|terms of service)\b",
    r"^show hn:\s*$",
    r"^\s*(home|index|untitled)\s*$",
)

_LOW_SIGNAL_PATTERNS = (
    r"\b(bitcoin|btc|crypto|cryptocurrency|wallet|password|decrypt)\b",
    r"\b(gop|democrat|republican|election|lawsuit|under scrutiny)\b",
    r"\b(account suspended|seconds after purchase|customer support)\b",
)

_STRONG_AI_PATTERNS = (
    r"\b(ai|artificial intelligence|llm|large language model|rag|mcp)\b",
    r"\b(openai|anthropic|claude|deepmind|gemini|qwen|deepseek)\b",
    r"\b(agentic|autonomous agent|ai agent|llm agent|multi-agent|tool calling|reasoning)\b",
    r"\b(transformer|diffusion|neural|machine learning|embedding|inference|fine-?tuning)\b",
)

_AMBIGUOUS_AGENT_PATTERNS = (
    r"\b(monitoring|logging|metrics|observability|telemetry)\s+agent\b",
    r"\b(data collection|collector|collection)\s+agent\b",
    r"\b(user|browser|software|desktop|network|security|backup|build|deployment)\s+agent\b",
    r"\b(agent for (monitoring|logging|metrics|data collection|telemetry))\b",
)


@dataclass(frozen=True)
class CandidateScore:
    score: float
    score_reasons: list[str]


def _safe_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _keyword_hits(text: str) -> list[str]:
    lowered = text.lower()
    return [keyword for keyword in _TOPIC_KEYWORDS if keyword in lowered]


def _freshness_score(published_at: datetime | str | None) -> tuple[float, str | None]:
    published = parse_candidate_datetime(published_at)
    if published is None:
        return 0.0, None

    now = datetime.now(tz=published.tzinfo) if published.tzinfo else datetime.now()
    if published.tzinfo is not None and now.tzinfo is None:
        now = datetime.now(timezone.utc)
    try:
        age_hours = max(0.0, (now - published).total_seconds() / 3600)
    except TypeError:
        return 0.0, None

    if age_hours <= 24:
        return 1.2, "fresh<=24h"
    if age_hours <= 72:
        return 0.7, "fresh<=72h"
    if age_hours <= 168:
        return 0.25, "fresh<=7d"
    return -0.4, "stale>7d"


def _engagement_score(item: CandidateNews) -> tuple[float, list[str]]:
    text = f"{item.summary_or_snippet or ''} {item.content_text or ''}".lower()
    reasons: list[str] = []
    score = 0.0

    points_match = re.search(r"\bpoints=(\d+)\b", text)
    comments_match = re.search(r"\bcomments=(\d+)\b", text)
    if points_match:
        points = int(points_match.group(1))
        bump = min(1.2, math.log10(points + 1) * 0.45)
        score += bump
        reasons.append(f"hn_points={points}")
    if comments_match:
        comments = int(comments_match.group(1))
        bump = min(0.8, math.log10(comments + 1) * 0.35)
        score += bump
        reasons.append(f"hn_comments={comments}")

    stars_match = re.search(r"\b(?:stars?|stargazers?)[:=]\s*([0-9][0-9,]*)\b", text)
    if stars_match:
        stars = int(stars_match.group(1).replace(",", ""))
        bump = min(1.0, math.log10(stars + 1) * 0.25)
        score += bump
        reasons.append(f"github_stars={stars}")

    return score, reasons


def is_noise_title(title: str) -> bool:
    lowered = _safe_text(title).lower()
    if not lowered:
        return True
    if len(lowered) < 8:
        return True
    return any(re.search(pattern, lowered) for pattern in _NOISE_TITLE_PATTERNS)


def is_low_signal_title(title: str) -> bool:
    lowered = _safe_text(title).lower()
    return any(re.search(pattern, lowered) for pattern in _LOW_SIGNAL_PATTERNS)


def has_strong_ai_evidence(text: str) -> bool:
    lowered = _safe_text(text).lower()
    return any(re.search(pattern, lowered) for pattern in _STRONG_AI_PATTERNS)


def has_ambiguous_non_ai_agent_context(text: str) -> bool:
    lowered = _safe_text(text).lower()
    return any(re.search(pattern, lowered) for pattern in _AMBIGUOUS_AGENT_PATTERNS)


def is_probable_ai_github_project(title: str, description: str = "") -> bool:
    text = f"{title} {description}"
    if not has_strong_ai_evidence(text):
        return False
    if has_ambiguous_non_ai_agent_context(text) and not re.search(
        r"\b(ai|llm|agentic|openai|claude|gemini|rag|mcp|reasoning|tool calling)\b",
        text.lower(),
    ):
        return False
    return True


def score_candidate(item: CandidateNews) -> CandidateScore:
    title = _safe_text(item.title)
    summary = _safe_text(item.summary_or_snippet)
    content = _safe_text(item.content_text)
    source_type = (item.source_type or "").strip()

    score = 0.0
    reasons: list[str] = []

    source_weight = _SOURCE_WEIGHTS.get(source_type, 0.75)
    score += source_weight
    reasons.append(f"source_type={source_type or 'unknown'}:+{source_weight:.2f}")

    if source_type == "hn_algolia":
        # HN search candidates can carry query terms in metadata, so use the title
        # itself for topic matching to avoid promoting unrelated high-engagement links.
        searchable = title
    else:
        searchable = f"{title} {summary} {' '.join(item.tags_hint or [])}"
    hits = _keyword_hits(searchable)
    if hits:
        bump = min(1.6, 0.35 * len(hits))
        score += bump
        reasons.append(f"topic_hits={','.join(hits[:4])}:+{bump:.2f}")
    elif source_type == "hn_algolia":
        score -= 3.0
        reasons.append("no_topic_hit_for_hn_title:-3.00")
    elif source_type in {"rss", "rss_or_web"}:
        score -= 1.5
        reasons.append("no_topic_hit_for_general_source:-1.50")

    if source_type == "github_trending" and not is_probable_ai_github_project(title, summary):
        score -= 3.5
        reasons.append("github_ambiguous_agent_or_weak_ai_evidence:-3.50")
    elif source_type == "github_trending" and has_ambiguous_non_ai_agent_context(f"{title} {summary}"):
        score -= 1.0
        reasons.append("github_ambiguous_agent_context:-1.00")

    if item.published_at:
        score += 0.55
        reasons.append("has_published_at:+0.55")
    freshness, freshness_reason = _freshness_score(item.published_at)
    if freshness:
        score += freshness
    if freshness_reason:
        reasons.append(f"{freshness_reason}:{freshness:+.2f}")

    title_len = len(title)
    if 25 <= title_len <= 130:
        score += 0.7
        reasons.append("title_length_good:+0.70")
    elif 12 <= title_len < 25 or 130 < title_len <= 180:
        score += 0.25
        reasons.append("title_length_ok:+0.25")
    else:
        score -= 0.6
        reasons.append("title_length_poor:-0.60")

    if summary:
        score += 0.45
        reasons.append("has_summary:+0.45")
    if content:
        score += 0.35
        reasons.append("has_content:+0.35")

    if is_noise_title(title):
        score -= 2.0
        reasons.append("noise_title:-2.00")
    if is_low_signal_title(title):
        score -= 2.5
        reasons.append("low_signal_or_sensitive_title:-2.50")

    engagement, engagement_reasons = _engagement_score(item)
    if engagement:
        score += engagement
    reasons.extend(engagement_reasons)

    return CandidateScore(score=round(score, 4), score_reasons=reasons)

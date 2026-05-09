from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    name: str
    type: str
    region: str = 'global'
    language: str = 'en'
    category: str = 'ai'
    content_type: str = 'media'
    priority: int = 1
    url_or_endpoint: str = ''
    max_items: Optional[int] = None
    timeout_seconds: int = 20
    max_retries: int = 2
    request_interval_seconds: float = 0.8
    tags: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    enabled: bool = True
    notes: Optional[str] = None


class CandidateNews(BaseModel):
    id: str
    title: str
    url: str
    source_name: str
    source_type: str
    region: str = 'global'
    language: str = 'en'
    category_hint: Optional[str] = None
    published_at: datetime | str | None = None
    summary_or_snippet: Optional[str] = None
    content_text: Optional[str] = None
    tags_hint: list[str] = Field(default_factory=list)


class DigestNewsItem(BaseModel):
    title: str
    links: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    summary: str = ''
    why_it_matters: str = ''
    insights: str = ''
    source_names: list[str] = Field(default_factory=list)


class CategoryGroup(BaseModel):
    category_name: str
    items: list[DigestNewsItem] = Field(default_factory=list)


class AppendixItem(BaseModel):
    title: str
    link: str
    source: str
    brief_summary: str = ''


class SourceStatistics(BaseModel):
    total_candidates: int = 0
    cleaned_candidates: int = 0
    selected_items: int = 0
    source_count: int = 0
    international_count: Optional[int] = None
    chinese_count: Optional[int] = None

    raw_candidates: Optional[int] = None
    cluster_input_candidates: Optional[int] = None
    event_clusters: Optional[int] = None
    final_llm_events: Optional[int] = None
    appendix_items: Optional[int] = None


class DailyDigest(BaseModel):
    date: str
    topic: str
    main_digest: list[CategoryGroup] = Field(default_factory=list)
    appendix: list[AppendixItem] = Field(default_factory=list)
    source_statistics: SourceStatistics = Field(default_factory=SourceStatistics)

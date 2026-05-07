from __future__ import annotations

from abc import ABC, abstractmethod
from hashlib import sha1
from typing import Any

from src.models import CandidateNews, SourceConfig


class BaseFetcher(ABC):
    def __init__(self, source_config: SourceConfig | dict[str, Any]) -> None:
        if isinstance(source_config, SourceConfig):
            self.source_config = source_config
        else:
            self.source_config = SourceConfig(**source_config)

    @abstractmethod
    def fetch(self) -> list[CandidateNews]:
        """Fetch candidate news and normalize to CandidateNews."""

    def build_candidate_id(self, url: str) -> str:
        raw = f"{self.source_config.name}|{url}".encode("utf-8", errors="ignore")
        return sha1(raw).hexdigest()[:16]

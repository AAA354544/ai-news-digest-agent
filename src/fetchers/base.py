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
        self.last_status: str = 'init'
        self.last_note: str = ''

    @abstractmethod
    def fetch(self, topic: str | None = None) -> list[CandidateNews]:
        """Fetch candidate news and normalize to CandidateNews."""

    def build_candidate_id(self, url: str) -> str:
        raw = f"{self.source_config.name}|{url}".encode('utf-8', errors='ignore')
        return sha1(raw).hexdigest()[:16]

    def set_health(self, status: str, note: str = '') -> None:
        self.last_status = status
        self.last_note = note

    def get_health(self) -> dict[str, str]:
        return {'status': self.last_status, 'note': self.last_note}

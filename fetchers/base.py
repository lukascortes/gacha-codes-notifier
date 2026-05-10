from abc import ABC, abstractmethod

from models import Code


class BaseFetcher(ABC):
    """Interface for game code fetchers. Each fetcher must be fail-soft:
    if the source is down or returns garbage, it logs and returns []."""

    game: str

    @abstractmethod
    def fetch(self) -> list[Code]:
        ...

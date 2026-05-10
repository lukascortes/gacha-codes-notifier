from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Reward:
    item: str
    quantity: int


@dataclass
class Code:
    code: str
    game: str
    rewards: list[Reward] = field(default_factory=list)
    source: str = ""
    discovered_at: str = ""
    expires_at: Optional[str] = None

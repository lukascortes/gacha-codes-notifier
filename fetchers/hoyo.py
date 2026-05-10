import logging
from datetime import datetime, timezone
from typing import Optional

import requests

from fetchers.base import BaseFetcher
from models import Code, Reward

log = logging.getLogger(__name__)

API_BASE = "https://hoyo-codes.seria.moe/codes"
TIMEOUT = 15

GAME_TO_API_KEY = {
    "genshin": "genshin",
    "hkrpg": "hkrpg",
    "nap": "nap",
}


def _parse_rewards(raw: Optional[str]) -> list[Reward]:
    """Parse strings like '50 Primogems, 5 Hero's Wit' into Reward list.
    Best-effort: if a chunk doesn't start with a number, store quantity=0."""
    if not raw:
        return []
    rewards: list[Reward] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split(" ", 1)
        try:
            qty = int(parts[0].replace(",", "").replace("x", ""))
            item = parts[1].strip() if len(parts) > 1 else chunk
        except (ValueError, IndexError):
            qty = 0
            item = chunk
        rewards.append(Reward(item=item, quantity=qty))
    return rewards


class HoyoFetcher(BaseFetcher):
    def __init__(self, game: str):
        if game not in GAME_TO_API_KEY:
            raise ValueError(f"Unsupported hoyo game: {game}")
        self.game = game

    def fetch(self) -> list[Code]:
        api_key = GAME_TO_API_KEY[self.game]
        url = f"{API_BASE}?game={api_key}"
        try:
            resp = requests.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            payload = resp.json()
        except (requests.RequestException, ValueError) as e:
            log.warning("Hoyo fetch failed for %s: %s", self.game, e)
            return []

        raw_codes = payload.get("codes", [])
        now = datetime.now(timezone.utc).isoformat()
        results: list[Code] = []
        for entry in raw_codes:
            if entry.get("status") != "OK":
                continue
            code = entry.get("code")
            if not code:
                continue
            results.append(
                Code(
                    code=code,
                    game=self.game,
                    rewards=_parse_rewards(entry.get("rewards")),
                    source=url,
                    discovered_at=now,
                )
            )
        log.info("Hoyo %s: fetched %d active codes", self.game, len(results))
        return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    )
    for g in ("genshin", "hkrpg", "nap"):
        fetcher = HoyoFetcher(g)
        for c in fetcher.fetch():
            print(f"{c.game:10s} {c.code:30s} {c.rewards}")

import json
import logging
import os
import sys
from pathlib import Path

from discord_poster import post_code
from fetchers.base import BaseFetcher
from fetchers.hoyo import HoyoFetcher
from fetchers.wuwa import WuwaFetcher
from models import Code

log = logging.getLogger("check_codes")

STATE_PATH = Path(__file__).parent / "state.json"
MAX_CODES_PER_GAME = 100

GAMES = ("genshin", "hkrpg", "nap", "wuwa")

WEBHOOK_ENV = {
    "genshin": "DISCORD_WEBHOOK_GENSHIN",
    "hkrpg": "DISCORD_WEBHOOK_HSR",
    "nap": "DISCORD_WEBHOOK_ZZZ",
    "wuwa": "DISCORD_WEBHOOK_WUWA",
}

ROLE_PING_ENV = "DISCORD_PING_ROLE_ID"


def load_state() -> tuple[dict[str, list[str]], bool]:
    """Return (state, is_first_run). On first run, returns empty state."""
    if not STATE_PATH.exists():
        log.info("state.json not found — first run, will initialize without posting")
        return ({game: [] for game in GAMES}, True)
    try:
        with STATE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        log.error("Failed to read state.json (%s) — treating as first run", e)
        return ({game: [] for game in GAMES}, True)

    for game in GAMES:
        data.setdefault(game, [])
    return (data, False)


def save_state(state: dict[str, list[str]]) -> None:
    for game in GAMES:
        if len(state.get(game, [])) > MAX_CODES_PER_GAME:
            state[game] = state[game][-MAX_CODES_PER_GAME:]
    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")


def build_fetchers() -> list[BaseFetcher]:
    return [
        HoyoFetcher("genshin"),
        # HoyoFetcher("hkrpg"),  # disabled — re-enable when DISCORD_WEBHOOK_HSR is set
        # HoyoFetcher("nap"),    # disabled — re-enable when DISCORD_WEBHOOK_ZZZ is set
        WuwaFetcher(),
    ]


def process_game(
    game: str,
    fetched: list[Code],
    state: dict[str, list[str]],
    is_first_run: bool,
    role_id: str | None,
) -> None:
    known = set(state.get(game, []))
    new_codes = [c for c in fetched if c.code not in known]

    if not new_codes:
        log.info("%s: no new codes", game)
        return

    if is_first_run:
        log.info("%s: first run, initializing %d codes silently", game, len(new_codes))
        state[game] = list(state.get(game, [])) + [c.code for c in new_codes]
        return

    webhook_env = WEBHOOK_ENV[game]
    webhook = os.environ.get(webhook_env)
    if not webhook:
        log.info("%s: %s not set, skipping post for %d new codes",
                 game, webhook_env, len(new_codes))
        return

    for code in new_codes:
        if post_code(webhook, code, role_id=role_id):
            state.setdefault(game, []).append(code.code)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    )

    state, is_first_run = load_state()
    role_id = os.environ.get(ROLE_PING_ENV)

    by_game: dict[str, list[Code]] = {g: [] for g in GAMES}
    for fetcher in build_fetchers():
        try:
            codes = fetcher.fetch()
        except Exception as e:
            log.exception("Fetcher for %s crashed: %s", fetcher.game, e)
            codes = []
        by_game.setdefault(fetcher.game, []).extend(codes)

    for game in GAMES:
        process_game(game, by_game.get(game, []), state, is_first_run, role_id)

    save_state(state)
    log.info("Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())

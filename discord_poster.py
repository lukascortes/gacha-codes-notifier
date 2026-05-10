import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import requests

from models import Code

log = logging.getLogger(__name__)

TIMEOUT = 15

GAME_META = {
    "genshin": {
        "name": "Genshin Impact",
        "emoji": "\U0001F338",
        "color": 0x4A90E2,
        "redeem_url": "https://genshin.hoyoverse.com/en/gift?code={code}",
        "how_to": "Paimon Menu → Settings → Account → Redeem Code",
    },
    "hkrpg": {
        "name": "Honkai Star Rail",
        "emoji": "\U0001F682",
        "color": 0x8B5CF6,
        "redeem_url": "https://hsr.hoyoverse.com/gift?code={code}",
        "how_to": "Phone Menu → ... → Redemption Code",
    },
    "nap": {
        "name": "Zenless Zone Zero",
        "emoji": "⚡",
        "color": 0xEAB308,
        "redeem_url": "https://zenless.hoyoverse.com/redemption?code={code}",
        "how_to": "Main Menu → More → Redemption Code",
    },
    "wuwa": {
        "name": "Wuthering Waves",
        "emoji": "\U0001F30A",
        "color": 0x06B6D4,
        "redeem_url": None,
        "how_to": "Terminal → Settings → Other Settings → Redemption Code",
    },
}


def _format_rewards(code: Code) -> str:
    if not code.rewards:
        return "_See in-game for details_"
    lines = []
    for r in code.rewards:
        if r.quantity:
            lines.append(f"• {r.quantity} {r.item}")
        else:
            lines.append(f"• {r.item}")
    return "\n".join(lines)


def _source_label(source: str) -> str:
    if not source:
        return "unknown"
    try:
        return urlparse(source).netloc or source
    except Exception:
        return source


def build_embed(code: Code) -> dict:
    meta = GAME_META.get(code.game)
    if meta is None:
        raise ValueError(f"Unknown game: {code.game}")

    fields = [
        {"name": "Code", "value": f"`{code.code}`", "inline": False},
        {"name": "Rewards", "value": _format_rewards(code), "inline": False},
    ]

    if meta["redeem_url"]:
        url = meta["redeem_url"].format(code=code.code)
        fields.append({"name": "Redeem", "value": f"[Click here]({url})", "inline": False})

    fields.append({"name": "How to redeem", "value": meta["how_to"], "inline": False})

    return {
        "title": f"{meta['emoji']} New {meta['name']} Code!",
        "color": meta["color"],
        "fields": fields,
        "footer": {"text": f"Source: {_source_label(code.source)}"},
        "timestamp": code.discovered_at or datetime.now(timezone.utc).isoformat(),
    }


def post_code(webhook_url: str, code: Code, role_id: Optional[str] = None) -> bool:
    """POST a single code to a Discord webhook. Returns True on success."""
    embed = build_embed(code)
    payload: dict = {"embeds": [embed]}
    if role_id:
        payload["content"] = f"<@&{role_id}>"
        payload["allowed_mentions"] = {"roles": [role_id]}

    try:
        resp = requests.post(webhook_url, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("Discord POST failed for %s/%s: %s", code.game, code.code, e)
        return False

    log.info("Posted %s/%s to Discord", code.game, code.code)
    return True

import logging
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup, Tag

from fetchers.base import BaseFetcher
from models import Code, Reward

log = logging.getLogger(__name__)

WUTHERING_GG_URL = "https://wuthering.gg/codes"
GAME8_URL = "https://game8.co/games/Wuthering-Waves/archives/453149"
TIMEOUT = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) "
        "Gecko/20100101 Firefox/120.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_QTY_PATTERN = re.compile(r"^\s*(\d[\d,]*)\s*[x×*]?\s*", re.UNICODE)


def _parse_reward_text(text: str) -> Reward:
    """Parse 'QTY [×|x] ITEM' or 'QTY ITEM'. quantity=0 if no leading number."""
    text = text.strip()
    if not text:
        return Reward(item="", quantity=0)
    m = _QTY_PATTERN.match(text)
    if not m:
        return Reward(item=text, quantity=0)
    try:
        qty = int(m.group(1).replace(",", ""))
    except ValueError:
        return Reward(item=text, quantity=0)
    item = text[m.end():].strip()
    if not item:
        return Reward(item=text, quantity=0)
    return Reward(item=item, quantity=qty)


def _looks_like_code(s: str) -> bool:
    return 4 <= len(s) <= 25 and s.replace("-", "").replace("_", "").isalnum()


class WuwaFetcher(BaseFetcher):
    game = "wuwa"

    def fetch(self) -> list[Code]:
        try:
            codes = self._fetch_wuthering_gg()
            if codes:
                log.info("WuWa primary (wuthering.gg): %d active codes", len(codes))
                return codes
            log.info("WuWa primary returned 0 active codes — trying fallback")
        except Exception as e:
            log.warning("WuWa primary (wuthering.gg) failed: %s", e)

        try:
            codes = self._fetch_game8()
            if codes:
                log.info("WuWa fallback (game8.co): %d active codes", len(codes))
                return codes
            log.warning("WuWa: both sources returned 0 active codes")
            return []
        except Exception as e:
            log.warning("WuWa fallback (game8.co) failed: %s — giving up this run", e)
            return []

    def _fetch_wuthering_gg(self) -> list[Code]:
        resp = requests.get(WUTHERING_GG_URL, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")

        rows = soup.select("table.codes-table tr.active")
        now = datetime.now(timezone.utc).isoformat()
        results: list[Code] = []
        for row in rows:
            code_td = row.select_one("td.code")
            if code_td is None:
                continue
            code_str = code_td.get_text(strip=True)
            if not _looks_like_code(code_str):
                continue
            tds = row.find_all("td")
            reward_lis = tds[2].find_all("li") if len(tds) >= 3 else []
            rewards = [_parse_reward_text(li.get_text(strip=True)) for li in reward_lis]
            results.append(
                Code(
                    code=code_str,
                    game=self.game,
                    rewards=rewards,
                    source=WUTHERING_GG_URL,
                    discovered_at=now,
                )
            )
        return results

    def _fetch_game8(self) -> list[Code]:
        resp = requests.get(GAME8_URL, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")

        active_header = soup.find("h3", id="hm_1")
        if active_header is None:
            active_header = soup.find(
                lambda t: t.name in ("h2", "h3")
                and "active" in t.get_text(strip=True).lower()
            )
        if active_header is None:
            log.warning("game8.co: could not locate active codes section")
            return []

        expired_header = soup.find("h2", id="hl_4")
        if expired_header is None:
            expired_header = soup.find(
                lambda t: t.name in ("h2", "h3")
                and "expired" in t.get_text(strip=True).lower()
            )

        active_ul: Tag | None = None
        for sibling in active_header.find_all_next():
            if sibling is expired_header:
                break
            if sibling.name == "ul" and "a-list" in (sibling.get("class") or []):
                active_ul = sibling
                break

        if active_ul is None:
            log.warning("game8.co: no active <ul.a-list> found in active section")
            return []

        now = datetime.now(timezone.utc).isoformat()
        results: list[Code] = []
        for li in active_ul.select("li.a-listItem"):
            bold = li.find("b")
            if bold is None:
                continue
            code_str = bold.get_text(strip=True)
            if not _looks_like_code(code_str):
                continue
            full_text = li.get_text(" ", strip=True)
            after_code = full_text.replace(code_str, "", 1).strip()
            after_code = after_code.lstrip(" -–—:").strip()
            rewards = [_parse_reward_text(c) for c in after_code.split(",") if c.strip()]
            results.append(
                Code(
                    code=code_str,
                    game=self.game,
                    rewards=rewards,
                    source=GAME8_URL,
                    discovered_at=now,
                )
            )
        return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    )
    fetcher = WuwaFetcher()
    for c in fetcher.fetch():
        print(f"\n{c.code}  (source: {c.source})")
        for r in c.rewards:
            print(f"  • {r.quantity:>6,d}  {r.item}" if r.quantity else f"  • {r.item}")

# TorrentGalaxy (TGx) Source Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement TorrentGalaxy (TGx) as a standard media source in Meridian-X supporting RSS syndication, keyword search, mirror fallback, and strict FHD/4K resolution filtering.

**Architecture:** Create `src/meridian_x/sources/torrentgalaxy.py` implementing the 4 core standard interface methods (`discover`, `resolve`, `search`, `resolve_magnet`, `is_whitelisted_title`). Register `"torrentgalaxy"` and `"tgx"` in `sources/__init__.py`, update `config/settings.json.example`, and connect CLI routing.

**Tech Stack:** Python 3.12, BeautifulSoup4 (bs4), Requests, XML ElementTree, Pytest, transmission-rpc.

## Global Constraints

- All Python commands must run with `uv run`.
- Strictly adhere to the standard source interface signatures.
- Adhere to the terminology rule: do not use '성인', use '신사'.
- Enforce strict FHD/4K resolution filtering (`is_fhd_or_higher`).
- Support multi-mirror fallback and `ssh_alias: "lt"` proxying.

---

### Task 1: Core TorrentGalaxy Module with RSS Discovery & Resolution

**Files:**
- Create: `src/meridian_x/sources/torrentgalaxy.py`
- Modify: `src/meridian_x/sources/__init__.py`
- Test: `tests/test_torrentgalaxy.py`

**Interfaces:**
- Consumes: `meridian_x.classify.get_artist_folders`, `meridian_x.classify.get_studio_mappings`, `meridian_x.classify._normalize_name`, `meridian_x.core.is_fhd_or_higher`
- Produces: `discover(config: dict) -> list[dict]`, `resolve(item: dict, config: dict) -> dict | None`, `is_whitelisted_title(title: str, config: dict) -> bool`

- [ ] **Step 1: Write the failing tests for RSS discovery, title whitelisting, and remote fetch**

```python
# tests/test_torrentgalaxy.py
import pytest
from unittest.mock import patch, MagicMock
from meridian_x.sources import SOURCES
import meridian_x.sources.torrentgalaxy as tgx

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torrent="https://torrentgalaxy.to">
  <channel>
    <title>TorrentGalaxy RSS</title>
    <item>
      <title>Vixen 26 08 20 Angela White Passionate Night XXX 1080p MP4-WRB</title>
      <link>https://torrentgalaxy.to/torrent/150001/Vixen-26-08-20-Angela-White</link>
      <enclosure url="magnet:?xt=urn:btih:TGXHASH1&amp;dn=Vixen+Angela+White" length="2500000000" type="application/x-bittorrent" />
      <pubDate>Thu, 20 Aug 2026 12:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Random 720p Video Low Quality</title>
      <link>https://torrentgalaxy.to/torrent/150002/Random-720p</link>
      <enclosure url="magnet:?xt=urn:btih:TGXHASH2" length="1000000000" type="application/x-bittorrent" />
    </item>
  </channel>
</rss>
"""

def test_tgx_registration():
    assert "torrentgalaxy" in SOURCES
    assert "tgx" in SOURCES
    assert SOURCES["torrentgalaxy"] is tgx
    assert SOURCES["tgx"] is tgx

def test_tgx_is_whitelisted_title():
    config = {
        "classify": {
            "artists": {"WEST": {"Angela White": ["angela white"]}},
            "studios": {"WEST": {"Vixen": ["vixen"]}}
        }
    }
    # Whitelisted artist + 1080p -> True
    assert tgx.is_whitelisted_title("Vixen 26 08 20 Angela White XXX 1080p MP4-WRB", config) is True
    # Whitelisted studio + 4K -> True
    assert tgx.is_whitelisted_title("Vixen 4K UHD Special Release", config) is True
    # Low resolution 720p -> False
    assert tgx.is_whitelisted_title("Vixen 720p Angela White", config) is False
    # Non-whitelisted -> False
    assert tgx.is_whitelisted_title("Unknown Actress 1080p Release", config) is False

def test_tgx_discover_and_resolve():
    config = {
        "classify": {
            "artists": {"WEST": {"Angela White": ["angela white"]}},
            "studios": {"WEST": {"Vixen": ["vixen"]}}
        }
    }
    with patch.object(tgx, "_fetch_url", return_value=(True, SAMPLE_RSS)):
        items = tgx.discover(config)
        assert len(items) == 1
        assert items[0]["id"] == "tgx:150001"
        assert "Angela White" in items[0]["title"]
        assert items[0]["magnet_url"].startswith("magnet:?xt=urn:btih:TGXHASH1")

        resolved = tgx.resolve(items[0], config)
        assert resolved is not None
        assert resolved["magnet_url"] == items[0]["magnet_url"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_torrentgalaxy.py -v`
Expected: FAIL (ModuleNotFoundError or ImportError)

- [ ] **Step 3: Implement core TorrentGalaxy module and register in sources**

```python
# src/meridian_x/sources/torrentgalaxy.py
import html
import logging
import re
import shlex
import subprocess
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup

from meridian_x.classify import (
    _normalize_name,
    get_artist_folders,
    get_studio_mappings,
)
from meridian_x.core import is_fhd_or_higher

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://torrentgalaxy.to"
DEFAULT_MIRRORS = ["https://tgx.rs", "https://torrentgalaxy.mx", "https://torrentgalaxy.one"]
DEFAULT_CATEGORY = "42"


def _tgx_remote(config: dict) -> dict:
    return (
        config.get("sources", {}).get("torrentgalaxy", {}).get("remote")
        or config.get("sources", {}).get("tgx", {}).get("remote")
        or config.get("remote", {})
    )


def _safe_timeout(config: dict) -> int:
    return int(
        config.get("sources", {}).get("torrentgalaxy", {}).get("request_timeout")
        or config.get("request_timeout")
        or 30
    )


def _ssh(remote: dict, cmd: str, timeout: int) -> tuple[bool, str]:
    if remote.get("ssh_alias"):
        ssh_cmd = ["ssh", "-o", "ConnectTimeout=5", remote["ssh_alias"], cmd]
    elif remote.get("host") and remote.get("user") and remote.get("ssh_key"):
        ssh_cmd = [
            "ssh",
            "-i",
            remote["ssh_key"],
            "-o",
            "ConnectTimeout=5",
            "-o",
            "StrictHostKeyChecking=no",
            f"{remote['user']}@{remote['host']}",
            cmd,
        ]
    else:
        return False, "SSH remote not configured"

    try:
        res = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
        if res.returncode == 0:
            return True, res.stdout
        return False, res.stderr or res.stdout
    except Exception as e:
        return False, str(e)


def _fetch_url(url: str, config: dict, candidate_urls: list[str] = None) -> tuple[bool, str]:
    timeout = _safe_timeout(config)
    remote = _tgx_remote(config)
    urls = [url]
    if candidate_urls:
        for u in candidate_urls:
            if u not in urls:
                urls.append(u)

    user_agent = config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    for target_url in urls:
        if remote and (remote.get("ssh_alias") or remote.get("host")):
            curl_cmd = f"curl -4 -sL --max-time {timeout} {shlex.quote(target_url)}"
            ok, out = _ssh(remote, curl_cmd, timeout + 10)
            if ok and out.strip():
                return True, out
            logger.warning(f"TorrentGalaxy fetch failed on {target_url[:60]} via remote: {out[:100]}")
        else:
            try:
                resp = requests.get(target_url, headers={"User-Agent": user_agent}, timeout=timeout)
                if resp.status_code == 200 and resp.text.strip():
                    return True, resp.text
            except Exception as e:
                logger.warning(f"TorrentGalaxy direct fetch failed on {target_url[:60]}: {e}")

    return False, "All candidate mirrors failed"


def is_whitelisted_title(title: str, config: dict) -> bool:
    """Check if title matches WEST artist, WEST studio, or genre keyword AND is FHD+."""
    if not is_fhd_or_higher(title):
        return False

    genres = config.get("genres", {})
    keywords = set(get_artist_folders(config, region="WEST"))
    for studio, aliases in get_studio_mappings(config, region="WEST").items():
        keywords.add(studio)
        keywords.update(aliases)

    for genre_name, rules in genres.items():
        keywords.add(genre_name)
        keywords.update(rules.get("keywords", []))
        keywords.update(rules.get("prefixes", []))

    norm_title = _normalize_name(title)
    for kw in keywords:
        if kw and _normalize_name(kw) in norm_title:
            return True
    return False


def _parse_rss(rss_content: str) -> list[dict]:
    items = []
    try:
        root = ET.fromstring(rss_content)
    except Exception as e:
        logger.error(f"Failed to parse TorrentGalaxy RSS XML: {e}")
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    for item_elem in channel.findall("item"):
        title_elem = item_elem.find("title")
        link_elem = item_elem.find("link")
        enclosure = item_elem.find("enclosure")
        if title_elem is None or link_elem is None:
            continue

        title = title_elem.text or ""
        link = link_elem.text or ""
        magnet_url = enclosure.attrib.get("url", "") if enclosure is not None else ""

        match = re.search(r'/torrent/(\d+)', link)
        tgx_id = match.group(1) if match else link.split("/")[-1]
        torrent_id = f"tgx:{tgx_id}"

        items.append({
            "id": torrent_id,
            "title": title,
            "page_url": link,
            "magnet_url": html.unescape(magnet_url),
        })
    return items


def discover(config: dict) -> list[dict]:
    rss_url = config.get("sources", {}).get("torrentgalaxy", {}).get("rss_url") or "https://torrentgalaxy.to/rss?cat=42"
    base_url = config.get("sources", {}).get("torrentgalaxy", {}).get("base_url") or DEFAULT_BASE_URL
    mirrors = config.get("sources", {}).get("torrentgalaxy", {}).get("mirrors") or DEFAULT_MIRRORS
    candidate_rss = [rss_url] + [f"{m.rstrip('/')}/rss?cat=42" for m in mirrors]

    ok, content = _fetch_url(rss_url, config, candidate_urls=candidate_rss)
    if not ok or not content:
        logger.error(f"TorrentGalaxy RSS discover failed: {content}")
        return []

    parsed = _parse_rss(content)
    return [item for item in parsed if is_whitelisted_title(item["title"], config)]


def resolve(item: dict, config: dict) -> dict | None:
    magnet = item.get("magnet_url")
    if magnet:
        return {"magnet_url": magnet, "metainfo": None}
    return None
```

```python
# src/meridian_x/sources/__init__.py
from . import onejav, xxxclub, sukebei, torrentgalaxy

SOURCES = {
    "onejav": onejav,
    "xxxclub": xxxclub,
    "sukebei": sukebei,
    "torrentgalaxy": torrentgalaxy,
    "tgx": torrentgalaxy,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_torrentgalaxy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/meridian_x/sources/torrentgalaxy.py src/meridian_x/sources/__init__.py tests/test_torrentgalaxy.py
git commit -m "feat(tgx): implement core TorrentGalaxy module with RSS discovery and resolution"
```

---

### Task 2: TGx Keyword Search & Direct Magnet Resolution

**Files:**
- Modify: `src/meridian_x/sources/torrentgalaxy.py`
- Modify: `tests/test_torrentgalaxy.py`

**Interfaces:**
- Consumes: `_fetch_url`, `is_fhd_or_higher`
- Produces: `search(query: str, category: str = "42", config: dict = None) -> list[dict]`, `resolve_magnet(item_or_details_url: dict | str, config: dict = None) -> str | None`

- [ ] **Step 1: Write failing tests for search and resolve_magnet**

```python
# Add to tests/test_torrentgalaxy.py
SAMPLE_SEARCH_HTML = """<!DOCTYPE html>
<html>
<body>
  <div class="tgxtable">
    <div class="tgxtablerow">
      <div class="tgxtablecell">
        <a href="/torrent/160001/Vixen-Angela-White-FHD" class="txlight"><b>Vixen.Angela.White.1080p.MP4</b></a>
      </div>
      <div class="tgxtablecell">
        <a href="magnet:?xt=urn:btih:SEARCHHASH1&amp;dn=Vixen.Angela.White" role="button"></a>
      </div>
      <div class="tgxtablecell"><span class="badge">2.45 GB</span></div>
      <div class="tgxtablecell"><font color="green"><b>45</b></font></div>
      <div class="tgxtablecell"><font color="brown">5</font></div>
    </div>
    <div class="tgxtablerow">
      <div class="tgxtablecell">
        <a href="/torrent/160002/Low-Quality-720p" class="txlight"><b>Low.Quality.720p.Video</b></a>
      </div>
      <div class="tgxtablecell">
        <a href="magnet:?xt=urn:btih:SEARCHHASH2" role="button"></a>
      </div>
      <div class="tgxtablecell"><span class="badge">900 MB</span></div>
      <div class="tgxtablecell"><font color="green"><b>10</b></font></div>
      <div class="tgxtablecell"><font color="brown">1</font></div>
    </div>
  </div>
</body>
</html>
"""

def test_tgx_search():
    with patch.object(tgx, "_fetch_url", return_value=(True, SAMPLE_SEARCH_HTML)):
        items = tgx.search("Angela White", category="42", config={})
        assert len(items) == 1
        assert items[0]["id"] == "tgx:160001"
        assert items[0]["title"] == "Vixen.Angela.White.1080p.MP4"
        assert items[0]["magnet_url"].startswith("magnet:?xt=urn:btih:SEARCHHASH1")
        assert items[0]["size"] == "2.45 GB"
        assert items[0]["seeders"] == "45"
        assert items[0]["leechers"] == "5"

def test_tgx_resolve_magnet():
    item = {"magnet_url": "magnet:?xt=urn:btih:TESTHASH"}
    assert tgx.resolve_magnet(item) == "magnet:?xt=urn:btih:TESTHASH"
    assert tgx.resolve_magnet("magnet:?xt=urn:btih:TESTHASH2") == "magnet:?xt=urn:btih:TESTHASH2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_torrentgalaxy.py::test_tgx_search -v`
Expected: FAIL (`AttributeError: module 'meridian_x.sources.torrentgalaxy' has no attribute 'search'`)

- [ ] **Step 3: Implement search and resolve_magnet in torrentgalaxy.py**

```python
# Add to src/meridian_x/sources/torrentgalaxy.py
from urllib.parse import quote_plus


def _parse_search_html(html_content: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html_content, "html.parser")
    items = []

    rows = soup.select("div.tgxtablerow")
    if not rows:
        rows = soup.select("table.table-striped tr, table tr")

    for row in rows:
        link_elem = row.select_one('a[href*="/torrent/"]')
        if not link_elem:
            continue

        href = link_elem.get("href", "")
        title = link_elem.get_text(strip=True)
        if not href or not title:
            continue

        match = re.search(r'/torrent/(\d+)', href)
        tgx_id = match.group(1) if match else href.split("/")[-1]
        torrent_id = f"tgx:{tgx_id}"

        details_url = f"{base_url.rstrip('/')}/{href.lstrip('/')}" if not href.startswith("http") else href

        magnet_elem = row.select_one('a[href^="magnet:"]')
        magnet_url = html.unescape(magnet_elem.get("href", "").strip()) if magnet_elem else ""

        size = ""
        size_elem = row.select_one("span.badge, td.size")
        if size_elem:
            size = size_elem.get_text(strip=True)

        seeders = "0"
        leechers = "0"
        font_greens = row.find_all("font", color="green") or row.select("font[color='green']")
        if font_greens:
            seeders = font_greens[0].get_text(strip=True)
        font_browns = row.find_all("font", color="brown") or row.select("font[color='brown']")
        if font_browns:
            leechers = font_browns[0].get_text(strip=True)

        items.append({
            "id": torrent_id,
            "title": title,
            "details_url": details_url,
            "magnet_url": magnet_url,
            "size": size,
            "seeders": seeders,
            "leechers": leechers,
        })

    if not config_allow_all_quality: # filtered by is_fhd_or_higher
        items = [item for item in items if is_fhd_or_higher(item["title"])]
    return items


def search(query: str, category: str = DEFAULT_CATEGORY, config: dict = None) -> list[dict]:
    config = config or {}
    base_url = config.get("sources", {}).get("torrentgalaxy", {}).get("base_url") or DEFAULT_BASE_URL
    mirrors = config.get("sources", {}).get("torrentgalaxy", {}).get("mirrors") or DEFAULT_MIRRORS

    encoded_q = quote_plus(query)
    search_path = f"/torrents.php?search={encoded_q}&cat={category}&sort=seeders&order=desc"
    search_url = f"{base_url.rstrip('/')}{search_path}"
    candidate_urls = [search_url] + [f"{m.rstrip('/')}{search_path}" for m in mirrors]

    ok, content = _fetch_url(search_url, config, candidate_urls=candidate_urls)
    if not ok or not content:
        logger.error(f"TorrentGalaxy search failed for query '{query}': {content}")
        return []

    soup = BeautifulSoup(content, "html.parser")
    items = []
    for row in soup.select("div.tgxtablerow"):
        link_elem = row.select_one('a[href*="/torrent/"]')
        if not link_elem:
            continue
        href = link_elem.get("href", "")
        title = link_elem.get_text(strip=True)
        if not title:
            continue
        match = re.search(r'/torrent/(\d+)', href)
        tgx_id = match.group(1) if match else href.split("/")[-1]
        torrent_id = f"tgx:{tgx_id}"
        details_url = f"{base_url.rstrip('/')}/{href.lstrip('/')}" if not href.startswith("http") else href

        magnet_elem = row.select_one('a[href^="magnet:"]')
        magnet_url = html.unescape(magnet_elem.get("href", "").strip()) if magnet_elem else ""

        size = ""
        size_elem = row.select_one("span.badge")
        if size_elem:
            size = size_elem.get_text(strip=True)

        seeders = "0"
        leechers = "0"
        font_g = row.find_all("font", color="green")
        if font_g:
            seeders = font_g[0].get_text(strip=True)
        font_b = row.find_all("font", color="brown")
        if font_b:
            leechers = font_b[0].get_text(strip=True)

        items.append({
            "id": torrent_id,
            "title": title,
            "details_url": details_url,
            "magnet_url": magnet_url,
            "size": size,
            "seeders": seeders,
            "leechers": leechers,
        })

    if not config.get("allow_all_quality", False):
        items = [item for item in items if is_fhd_or_higher(item["title"])]

    return items


def resolve_magnet(item_or_details_url: dict | str, config: dict = None) -> str | None:
    if isinstance(item_or_details_url, dict):
        if item_or_details_url.get("magnet_url"):
            return item_or_details_url["magnet_url"]
        url = item_or_details_url.get("details_url") or item_or_details_url.get("page_url")
    else:
        url = item_or_details_url

    if not url:
        return None
    if url.startswith("magnet:"):
        return url

    config = config or {}
    ok, content = _fetch_url(url, config)
    if not ok or not content:
        return None

    soup = BeautifulSoup(content, "html.parser")
    magnet_elem = soup.select_one('a[href^="magnet:"]')
    if magnet_elem:
        return html.unescape(magnet_elem.get("href", "").strip())
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_torrentgalaxy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/meridian_x/sources/torrentgalaxy.py tests/test_torrentgalaxy.py
git commit -m "feat(tgx): implement keyword search and magnet resolution with FHD/4K filtering"
```

---

### Task 3: CLI Integration, Settings Example & Documentation

**Files:**
- Modify: `config/settings.json.example`
- Modify: `src/meridian_x/cli.py`
- Modify: `.ai/RULES.md`
- Test: `tests/test_torrentgalaxy.py`

**Interfaces:**
- Consumes: `SOURCES["torrentgalaxy"]`, `run_search`
- Produces: CLI support for `meridian search "<query>" --source tgx`

- [ ] **Step 1: Write failing CLI integration test**

```python
# Add to tests/test_torrentgalaxy.py
def test_tgx_cli_search_auto_mode(monkeypatch):
    from meridian_x.cli import run_search
    fake_items = [{
        "id": "tgx:170001",
        "title": "Vixen Angela White 1080p",
        "size": "2.1 GB",
        "seeders": "50",
        "leechers": "2",
        "magnet_url": "magnet:?xt=urn:btih:CLIHASH",
        "details_url": "https://torrentgalaxy.to/torrent/170001"
    }]
    with patch("meridian_x.sources.torrentgalaxy.search", return_value=fake_items), \
         patch("meridian_x.db.MeridianDB.is_downloaded", return_value=False), \
         patch("meridian_x.db.MeridianDB.add_download_history"), \
         patch("meridian_x.transmission.TransmissionClient.add_magnet", return_value=True):
        count = run_search(query="Angela White", source="tgx", auto=True, delay=0)
        assert count == 1
```

- [ ] **Step 2: Run test to verify it passes or check CLI category default**

Run: `uv run pytest tests/test_torrentgalaxy.py::test_tgx_cli_search_auto_mode -v`

- [ ] **Step 3: Update `settings.json.example` and `.ai/RULES.md`**

Add `torrentgalaxy` block to `config/settings.json.example`:
```json
"torrentgalaxy": {
  "enabled": true,
  "base_url": "https://torrentgalaxy.to",
  "mirrors": [
    "https://tgx.rs",
    "https://torrentgalaxy.mx"
  ],
  "rss_url": "https://torrentgalaxy.to/rss?cat=42",
  "default_category": "42",
  "remote": {
    "ssh_alias": "lt"
  },
  "request_timeout": 30,
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
```

Update `.ai/RULES.md` CLI examples and architecture with TorrentGalaxy (TGx).

- [ ] **Step 4: Run full regression test suite**

Run: `uv run pytest tests/`
Expected: 100% pass

- [ ] **Step 5: Commit**

```bash
git add config/settings.json.example src/meridian_x/cli.py .ai/RULES.md tests/test_torrentgalaxy.py
git commit -m "feat: integrate TorrentGalaxy source into CLI, settings template, and rules"
```

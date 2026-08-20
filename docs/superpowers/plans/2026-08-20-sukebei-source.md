# Sukebei (Nyaa) Source Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Meridian-X에 신사 실사(JAV/FC2/무수정) P2P 인덱서인 Sukebei(`sukebei.nyaa.si`) 소스를 추가하여 RSS 자동 수집(`meridian transmission --source sukebei`) 및 키워드/품번 검색(`meridian search <query> --source sukebei`)을 지원한다.

**Architecture:** OneJAV 및 XXXClub과 동일한 4대 표준 소스 인터페이스(`discover`, `resolve`, `search`, `resolve_magnet`)를 구현하고, 한국 통신사 SNI 차단 환경을 고려해 SSH 원격 프록시(`lt`) 및 직접 통신을 투명하게 지원하는 `sukebei.py` 모듈을 작성하여 등록한다.

**Tech Stack:** Python 3.12, BeautifulSoup4, requests, pytest, Transmission RPC, regex

## Global Constraints

- Python 커맨드는 항상 `uv run`을 통해 가상환경 의존성 내에서 실행한다.
- 용어는 '신사' 표현을 준수한다.
- `SOURCES` 레지스트리 및 표준 소스 인터페이스(`discover`, `resolve`, `search`, `resolve_magnet`) 규격을 엄격히 준수한다.
- 변경 전/후 회귀 테스트 `uv run pytest tests/`를 통과해야 한다.

---

### Task 1: Sukebei Source Module - Network & RSS Discovery

**Files:**
- Create: `src/meridian_x/sources/sukebei.py`
- Modify: `src/meridian_x/sources/__init__.py`
- Test: `tests/test_sukebei.py`

**Interfaces:**
- Produces:
  - `sukebei.is_whitelisted_title(title: str, config: dict) -> bool`
  - `sukebei.discover(config: dict) -> list[dict]`
  - `sukebei.resolve(item: dict, config: dict) -> dict`

- [ ] **Step 1: Write failing test for RSS discovery and resolve**

Create `tests/test_sukebei.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from meridian_x.sources import sukebei


SAMPLE_SUKEBEI_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:nyaa="https://nyaa.si/xmlns/nyaa">
  <channel>
    <title>Sukebei - Real Life - Video</title>
    <link>https://sukebei.nyaa.si/</link>
    <description>RSS Feed for Sukebei</description>
    <item>
      <title>[FHD/3.2GB] MIAA-001 MINAMO Special Debut</title>
      <link>https://sukebei.nyaa.si/view/1234567</link>
      <guid isPermaLink="true">https://sukebei.nyaa.si/view/1234567</guid>
      <pubDate>Thu, 20 Aug 2026 00:00:00 +0000</pubDate>
      <nyaa:seeders>25</nyaa:seeders>
      <nyaa:leechers>3</nyaa:leechers>
      <nyaa:downloads>150</nyaa:downloads>
      <nyaa:infoHash>0123456789abcdef0123456789abcdef01234567</nyaa:infoHash>
      <nyaa:size>3.2 GiB</nyaa:size>
    </item>
    <item>
      <title>Unrelated Amateur Clip 9999</title>
      <link>https://sukebei.nyaa.si/view/1234568</link>
      <guid isPermaLink="true">https://sukebei.nyaa.si/view/1234568</guid>
      <pubDate>Thu, 20 Aug 2026 00:00:00 +0000</pubDate>
      <nyaa:seeders>5</nyaa:seeders>
      <nyaa:leechers>1</nyaa:leechers>
      <nyaa:downloads>10</nyaa:downloads>
      <nyaa:infoHash>abcdef0123456789abcdef0123456789abcdef01</nyaa:infoHash>
      <nyaa:size>500 MiB</nyaa:size>
    </item>
  </channel>
</rss>
"""


def test_is_whitelisted_title():
    config = {
        "classify": {
            "artists": {"JPN": ["MINAMO", "Rena Miyashita"]},
            "studios": {"JPN": {"S1": ["s1"]}},
        }
    }
    assert sukebei.is_whitelisted_title("MIAA-001 MINAMO Debut", config) is True
    assert sukebei.is_whitelisted_title("Random Title Without Match", config) is False


def test_sukebei_discover_and_resolve():
    config = {
        "rss_url": "https://sukebei.nyaa.si/?page=rss&c=2_2",
        "classify": {
            "artists": {"JPN": ["MINAMO"]},
            "studios": {},
        },
    }

    with patch.object(sukebei, "_fetch_url", return_value=(True, SAMPLE_SUKEBEI_RSS)):
        items = sukebei.discover(config)
        assert len(items) == 1
        item = items[0]
        assert item["id"] == "sukebei:1234567"
        assert "MINAMO" in item["title"]
        assert item["seeders"] == "25"
        assert item["size"] == "3.2 GiB"

        payload = sukebei.resolve(item, config)
        assert payload["type"] == "magnet"
        assert "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567" in payload["data"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sukebei.py -v`
Expected: FAIL (ModuleNotFoundError or AttributeError)

- [ ] **Step 3: Implement `src/meridian_x/sources/sukebei.py` discovery & resolve**

Create `src/meridian_x/sources/sukebei.py`:
```python
"""
Sukebei (Nyaa) Source for 신사 실사 (JAV/FC2/무수정)
RSS 수집 및 HTML 검색 → magnet link 추출
"""
import html
import logging
import re
import shlex
import subprocess
from urllib.parse import quote, urljoin, urlparse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
from meridian_x.classify import (
    _normalize_name,
    get_artist_folders,
    get_studio_mappings,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://sukebei.nyaa.si"
NYAA_NS = {"nyaa": "https://nyaa.si/xmlns/nyaa"}
JPN_CODE_PATTERN = re.compile(r'\b[A-Za-z]{2,8}[-_]?\d{3,5}\b|\bFC2[-_ ]?PPV[-_ ]?\d+\b', re.IGNORECASE)


def _safe_timeout(config: dict) -> int:
    try:
        timeout = int(config.get("request_timeout", 30))
        return max(1, timeout)
    except (ValueError, TypeError):
        return 30


def _ssh(remote: dict, cmd: str, timeout: int = 60) -> tuple[bool, str]:
    try:
        if remote.get("ssh_alias"):
            args = [
                "ssh",
                "-o", "ConnectTimeout=5",
                "-o", "StrictHostKeyChecking=no",
                remote["ssh_alias"],
                cmd,
            ]
        elif remote.get("host") and remote.get("user"):
            args = [
                "ssh",
                "-o", "ConnectTimeout=5",
                "-o", "StrictHostKeyChecking=no",
            ]
            if remote.get("ssh_key"):
                args.extend(["-i", remote["ssh_key"]])
            args.extend([f"{remote['user']}@{remote['host']}", cmd])
        else:
            return False, "SSH remote not configured"

        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return False, result.stderr or result.stdout
        return True, result.stdout
    except Exception as e:
        return False, str(e)


def _fetch_url(url: str, config: dict) -> tuple[bool, str]:
    timeout = _safe_timeout(config)
    remote = config.get("remote", {})
    if remote and (remote.get("ssh_alias") or remote.get("host")):
        curl_cmd = f"curl -4 -sL --max-time {timeout} {shlex.quote(url)}"
        return _ssh(remote, curl_cmd, timeout + 10)

    user_agent = config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    proxies = config.get("proxies") or ({"http": config["proxy"], "https": config["proxy"]} if config.get("proxy") else None)

    try:
        resp = requests.get(url, headers={"User-Agent": user_agent}, proxies=proxies, timeout=timeout)
        resp.raise_for_status()
        return True, resp.text
    except Exception as e:
        return False, str(e)


def is_whitelisted_title(title: str, config: dict) -> bool:
    """Check if title contains registered JPN favorite artist, JPN studio, or JPN code pattern."""
    keywords = set(get_artist_folders(config, region="JPN"))
    for studio, aliases in get_studio_mappings(config, region="JPN").items():
        keywords.add(studio)
        keywords.update(aliases)

    norm_title = _normalize_name(title)
    for kw in keywords:
        if kw and _normalize_name(kw) in norm_title:
            return True

    if JPN_CODE_PATTERN.search(title):
        return True

    return False


def _parse_rss(rss_content: str) -> list[dict]:
    items = []
    try:
        root = ET.fromstring(rss_content)
    except Exception as e:
        logger.error(f"Failed to parse Sukebei RSS XML: {e}")
        return []

    for item in root.findall(".//item"):
        title_elem = item.find("title")
        link_elem = item.find("link")
        guid_elem = item.find("guid")
        info_hash_elem = item.find("nyaa:infoHash", NYAA_NS)
        seeders_elem = item.find("nyaa:seeders", NYAA_NS)
        leechers_elem = item.find("nyaa:leechers", NYAA_NS)
        size_elem = item.find("nyaa:size", NYAA_NS)

        title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
        link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
        if not link and guid_elem is not None and guid_elem.text:
            link = guid_elem.text.strip()

        info_hash = info_hash_elem.text.strip() if info_hash_elem is not None and info_hash_elem.text else ""
        seeders = seeders_elem.text.strip() if seeders_elem is not None and seeders_elem.text else "0"
        leechers = leechers_elem.text.strip() if leechers_elem is not None and leechers_elem.text else "0"
        size = size_elem.text.strip() if size_elem is not None and size_elem.text else ""

        match = re.search(r'/view/(\d+)', link)
        sukebei_id = match.group(1) if match else link.split("/")[-1]
        torrent_id = f"sukebei:{sukebei_id}"

        magnet_url = f"magnet:?xt=urn:btih:{info_hash}&dn={quote(title)}" if info_hash else ""

        items.append({
            "id": torrent_id,
            "title": title,
            "details_url": link,
            "magnet_url": magnet_url,
            "info_hash": info_hash,
            "size": size,
            "seeders": seeders,
            "leechers": leechers,
        })
    return items


def discover(config: dict) -> list[dict]:
    """Sukebei RSS에서 항목 수집 및 화이트리스트 필터링."""
    rss_url = config.get("rss_url", f"{BASE_URL}/?page=rss&c=2_2")
    ok, content = _fetch_url(rss_url, config)
    if not ok or not content:
        logger.error(f"Sukebei RSS fetch failed: {content[:200] if content else 'empty response'}")
        return []

    items = _parse_rss(content)
    filtered = [item for item in items if is_whitelisted_title(item["title"], config)]
    return filtered


def resolve(item: dict, config: dict) -> dict | None:
    """Transmission 전송용 magnet payload 반환."""
    magnet = item.get("magnet_url")
    if not magnet and item.get("info_hash"):
        magnet = f"magnet:?xt=urn:btih:{item['info_hash']}&dn={quote(item.get('title', ''))}"

    if not magnet and item.get("details_url"):
        magnet = resolve_magnet(item["details_url"], config)

    if magnet:
        return {"type": "magnet", "data": magnet}
    return None
```

- [ ] **Step 4: Update `src/meridian_x/sources/__init__.py`**

Modify `src/meridian_x/sources/__init__.py`:
```python
from . import onejav, sukebei, xxxclub

SOURCES = {
    "onejav": onejav,
    "xxxclub": xxxclub,
    "sukebei": sukebei,
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_sukebei.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/meridian_x/sources/sukebei.py src/meridian_x/sources/__init__.py tests/test_sukebei.py
git commit -m "feat(sukebei): add sukebei source module with RSS discovery and resolve"
```

---

### Task 2: Sukebei Keyword & ID Search and Magnet Resolution

**Files:**
- Modify: `src/meridian_x/sources/sukebei.py`
- Test: `tests/test_sukebei.py`

**Interfaces:**
- Produces:
  - `sukebei.search(query: str, category: str = "2_2", config: dict = None) -> list[dict]`
  - `sukebei.resolve_magnet(details_url: str, config: dict = None) -> str | None`

- [ ] **Step 1: Write failing test for HTML search and magnet resolution**

Append to `tests/test_sukebei.py`:
```python
SAMPLE_SUKEBEI_SEARCH_HTML = """
<!DOCTYPE html>
<html>
<body>
<table class="table table-bordered table-hover table-striped torrent-list">
  <thead><tr><th>Category</th><th>Name</th><th>Link</th><th>Size</th><th>Date</th><th>Seeders</th><th>Leechers</th><th>Downloads</th></tr></thead>
  <tbody>
    <tr class="default">
      <td><a href="/?c=2_2" title="Real Life - Video">Video</a></td>
      <td colspan="2">
        <a href="/view/999888" title="MIAA-001 MINAMO Debut 1080p">MIAA-001 MINAMO Debut 1080p</a>
      </td>
      <td class="text-center">
        <a href="/download/999888.torrent"><i class="fa fa-download"></i></a>
        <a href="magnet:?xt=urn:btih:mockhash1234567890abcdef1234567890abcdef&amp;dn=MIAA-001"><i class="fa fa-magnet"></i></a>
      </td>
      <td class="text-center">4.5 GiB</td>
      <td class="text-center">2026-08-20</td>
      <td class="text-center">42</td>
      <td class="text-center">5</td>
      <td class="text-center">300</td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""


def test_sukebei_search():
    config = {}
    with patch.object(sukebei, "_fetch_url", return_value=(True, SAMPLE_SUKEBEI_SEARCH_HTML)):
        results = sukebei.search("MIAA-001", category="2_2", config=config)
        assert len(results) == 1
        res = results[0]
        assert res["id"] == "sukebei:999888"
        assert "MIAA-001" in res["title"]
        assert res["seeders"] == "42"
        assert res["size"] == "4.5 GiB"
        assert res["details_url"] == "https://sukebei.nyaa.si/view/999888"
        assert res["magnet_url"] == "magnet:?xt=urn:btih:mockhash1234567890abcdef1234567890abcdef&dn=MIAA-001"


def test_sukebei_resolve_magnet_from_page():
    page_html = '<a href="magnet:?xt=urn:btih:detailhash999&amp;dn=Sample">Magnet</a>'
    with patch.object(sukebei, "_fetch_url", return_value=(True, page_html)):
        magnet = sukebei.resolve_magnet("https://sukebei.nyaa.si/view/999888")
        assert magnet == "magnet:?xt=urn:btih:detailhash999&dn=Sample"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sukebei.py -k "test_sukebei_search or test_sukebei_resolve_magnet_from_page" -v`
Expected: FAIL (search/resolve_magnet not implemented or empty)

- [ ] **Step 3: Implement `search()` and `resolve_magnet()` in `src/meridian_x/sources/sukebei.py`**

Add to `src/meridian_x/sources/sukebei.py`:
```python
def search(query: str, category: str = "2_2", config: dict = None) -> list[dict]:
    """Sukebei 키워드/품번 검색 결과 반환."""
    if config is None:
        config = {}

    encoded_query = quote(query)
    cat_param = category if category else "2_2"
    search_url = f"{BASE_URL}/?f=0&c={cat_param}&q={encoded_query}&s=seeders&o=desc"

    ok, html_text = _fetch_url(search_url, config)
    if not ok or not html_text:
        logger.error(f"Sukebei search request failed for '{query}': {html_text[:200] if html_text else 'empty response'}")
        return []

    soup = BeautifulSoup(html_text, "html.parser")
    items = []

    for row in soup.select("table.torrent-list tbody tr"):
        links = row.select("td a[href*='/view/']")
        name_elem = None
        for a in links:
            if "comments" not in a.get("class", []):
                name_elem = a
                break

        if not name_elem or not name_elem.get("href"):
            continue

        href = name_elem.get("href")
        details_url = urljoin(BASE_URL, href)
        title = name_elem.get("title", "") or name_elem.get_text(strip=True)

        match = re.search(r'/view/(\d+)', href)
        slug_id = match.group(1) if match else href.split("/")[-1]
        torrent_id = f"sukebei:{slug_id}"

        magnet_elem = row.select_one("a[href^='magnet:']")
        magnet_url = html.unescape(magnet_elem.get("href")) if magnet_elem else ""

        cols = row.find_all("td")
        size = cols[3].get_text(strip=True) if len(cols) > 3 else ""
        seeders = cols[5].get_text(strip=True) if len(cols) > 5 else "0"
        leechers = cols[6].get_text(strip=True) if len(cols) > 6 else "0"

        items.append({
            "id": torrent_id,
            "title": title,
            "details_url": details_url,
            "magnet_url": magnet_url,
            "size": size,
            "seeders": seeders,
            "leechers": leechers,
        })

    return items


def resolve_magnet(details_url: str, config: dict = None) -> str | None:
    """상세 페이지 URL에서 magnet link 추출."""
    if config is None:
        config = {}

    ok, html_text = _fetch_url(details_url, config)
    if not ok or not html_text:
        logger.error(f"Sukebei details fetch failed for {details_url}")
        return None

    match = re.search(r'href=["\'](magnet:\?xt=urn:btih:[^"\']+)["\']', html_text, re.IGNORECASE)
    if match:
        return html.unescape(match.group(1))
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_sukebei.py -v`
Expected: PASS (All tests in `test_sukebei.py` pass)

- [ ] **Step 5: Commit**

```bash
git add src/meridian_x/sources/sukebei.py tests/test_sukebei.py
git commit -m "feat(sukebei): implement search and resolve_magnet functions"
```

---

### Task 3: CLI Integration & Configuration Template

**Files:**
- Modify: `config/settings.json.example`
- Modify: `src/meridian_x/cli.py`
- Test: `tests/test_sukebei.py`

**Interfaces:**
- CLI commands:
  - `meridian search <query> --source sukebei`
  - `meridian transmission --source sukebei`

- [ ] **Step 1: Write failing CLI integration test for Sukebei**

Append to `tests/test_sukebei.py`:
```python
from meridian_x.cli import run_search


def test_run_search_sukebei_auto_mode():
    mock_results = [
        {
            "id": "sukebei:12345",
            "title": "MIAA-001 MINAMO",
            "details_url": "https://sukebei.nyaa.si/view/12345",
            "magnet_url": "magnet:?xt=urn:btih:mockhash",
            "size": "4.0 GiB",
            "seeders": "20",
            "leechers": "2",
        }
    ]

    with patch("meridian_x.cli.SOURCES", {"sukebei": sukebei}), \
         patch.object(sukebei, "search", return_value=mock_results), \
         patch("meridian_x.cli.get_transmission_client") as mock_get_tx, \
         patch("meridian_x.cli.get_db") as mock_get_db:

        mock_tx = MagicMock()
        mock_get_tx.return_value = mock_tx
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        count = run_search(query="MIAA-001", source="sukebei", auto=True, delay=0.0)

        assert count == 1
        mock_tx.add_torrent.assert_called_once_with("magnet:?xt=urn:btih:mockhash")
        mock_db.add_download_history.assert_called_once_with(["sukebei:12345"])
```

- [ ] **Step 2: Update `config/settings.json.example`**

Add `sukebei` to `sources` in `config/settings.json.example`:
```json
    "sukebei": {
      "enabled": true,
      "base_url": "https://sukebei.nyaa.si",
      "rss_url": "https://sukebei.nyaa.si/?page=rss&c=2_2",
      "default_category": "2_2",
      "request_timeout": 30,
      "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
```

- [ ] **Step 3: Update `src/meridian_x/cli.py` category default handling for sukebei**

Ensure `category` default dynamically adapts to the source (e.g. `"2_2"` if `sukebei`, `"1080p"` if `xxxclub`) in `run_search()`.

- [ ] **Step 4: Run all tests to verify**

Run: `uv run pytest tests/test_sukebei.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config/settings.json.example src/meridian_x/cli.py tests/test_sukebei.py
git commit -m "feat(cli): integrate sukebei source into search command and settings template"
```

---

### Task 4: Full Regression & Documentation Update

**Files:**
- Modify: `.ai/RULES.md`
- Test: `tests/`

- [ ] **Step 1: Update `.ai/RULES.md`**

Add `sukebei` usage examples to `.ai/RULES.md`:
```bash
uv run meridian transmission --source sukebei
uv run meridian search "MIAA-001" --source sukebei
```

- [ ] **Step 2: Run complete test suite**

Run: `uv run pytest tests/ -v`
Expected: PASS (All tests pass)

- [ ] **Step 3: Commit**

```bash
git add .ai/RULES.md
git commit -m "docs: add sukebei commands and architecture rules to .ai/RULES.md"
```

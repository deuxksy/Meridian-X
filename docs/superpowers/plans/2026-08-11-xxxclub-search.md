# XXXClub 1080p Search & Transmission Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a search and transmission dispatch command (`meridian search <query>`) to search torrents by keyword in the 1080p category on XXXClub and download them via Transmission in both interactive and automated modes.

**Architecture:** Extend `src/meridian_x/sources/xxxclub.py` with `search()` and `resolve_magnet()` functions to handle HTML parsing of search results and detail pages. Update `src/meridian_x/cli.py` to register a new `search` command supporting `--auto`, `--interactive`, `--category`, and `--delay` options.

**Tech Stack:** Python 3.12, BeautifulSoup4 / html.parser, Requests, Pytest, MeridianDB, TransmissionClient.

## Global Constraints

- Use `uv run pytest` for running test suites.
- Follow KISS, YAGNI, DRY, TDD cycle (Red-Green-Refactor).
- In auto mode (`--auto`), enforce a configurable delay (default 5.0s) between detail page requests to prevent IP blocks.
- In interactive mode (default), user manually selects torrents by number, so no inter-request delay is required.

---

### Task 1: Extend `xxxclub.py` with Search and Magnet Extraction Functions

**Files:**
- Modify: `src/meridian_x/sources/xxxclub.py`
- Create: `tests/test_xxxclub_search.py`

**Interfaces:**
- Produces: 
  - `search(query: str, category: str = "1080p", config: dict = None) -> list[dict]`
    Returns list of `{"id": str, "title": str, "details_url": str, "size": str, "seeders": str, "leechers": str}`.
  - `resolve_magnet(details_url: str, config: dict = None) -> str | None`
    Returns `magnet:?xt=urn:btih:...` string or `None`.

- [ ] **Step 1: Write failing tests for `search` and `resolve_magnet`**

Create `tests/test_xxxclub_search.py`:
```python
from unittest.mock import patch, MagicMock
from meridian_x.sources.xxxclub import search, resolve_magnet

MOCK_SEARCH_HTML = """
<html>
<body>
  <table>
    <tr class="torrents-row">
      <td class="name"><a href="/details/12345/test-torrent-1080p">Test Torrent 1080p Title</a></td>
      <td class="size">1.5 GB</td>
      <td class="seeders">25</td>
      <td class="leechers">2</td>
    </tr>
  </table>
</body>
</html>
"""

MOCK_DETAILS_HTML = """
<html>
<body>
  <a href="magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=Test+Torrent">Download Magnet</a>
</body>
</html>
"""

def test_search_xxxclub():
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = MOCK_SEARCH_HTML
        mock_get.return_value = mock_response

        results = search("test", category="1080p", config={})
        assert len(results) == 1
        assert results[0]["title"] == "Test Torrent 1080p Title"
        assert results[0]["details_url"] == "https://xxxclub.to/details/12345/test-torrent-1080p"
        assert results[0]["size"] == "1.5 GB"
        assert results[0]["seeders"] == "25"
        assert results[0]["leechers"] == "2"

def test_resolve_magnet():
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = MOCK_DETAILS_HTML
        mock_get.return_value = mock_response

        magnet = resolve_magnet("https://xxxclub.to/details/12345/test-torrent-1080p", config={})
        assert magnet.startswith("magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678")
```

- [ ] **Step 2: Run pytest to verify failure**

Run: `uv run pytest tests/test_xxxclub_search.py -v`
Expected: FAIL (cannot import `search` / `resolve_magnet`)

- [ ] **Step 3: Implement `search` and `resolve_magnet` in `xxxclub.py`**

Add to `src/meridian_x/sources/xxxclub.py`:
```python
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin

BASE_URL = "https://xxxclub.to"

def search(query: str, category: str = "1080p", config: dict = None) -> list[dict]:
    """XXXClub 카테고리/키워드 검색 결과 반환."""
    if config is None:
        config = {}
    
    encoded_query = quote(query)
    search_url = f"{BASE_URL}/search/{category}/{encoded_query}"
    
    user_agent = config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    timeout = config.get("request_timeout", 30)
    
    try:
        response = requests.get(search_url, headers={"User-Agent": user_agent}, timeout=timeout)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"XXXClub search request failed for '{query}': {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    items = []
    
    # tr parsing (or specific row selectors based on site structure)
    for row in soup.select("tr.torrents-row, table tr"):
        name_elem = row.select_one("td.name a, a[href*='/details/']")
        if not name_elem or not name_elem.get("href"):
            continue
            
        href = name_elem.get("href")
        details_url = urljoin(BASE_URL, href)
        title = name_elem.get_text(strip=True)
        
        # Torrent ID generation
        hash_match = re.search(r'/details/([^/]+)', href)
        slug_id = hash_match.group(1) if hash_match else title
        torrent_id = f"xxxclub:{slug_id}"
        
        size_elem = row.select_one("td.size, td:nth-of-type(4)")
        seed_elem = row.select_one("td.seeders, td:nth-of-type(5)")
        leech_elem = row.select_one("td.leechers, td:nth-of-type(6)")
        
        size = size_elem.get_text(strip=True) if size_elem else ""
        seeders = seed_elem.get_text(strip=True) if seed_elem else "0"
        leechers = leech_elem.get_text(strip=True) if leech_elem else "0"
        
        items.append({
            "id": torrent_id,
            "title": title,
            "details_url": details_url,
            "size": size,
            "seeders": seeders,
            "leechers": leechers,
        })
        
    return items


def resolve_magnet(details_url: str, config: dict = None) -> str | None:
    """상세 페이지 URL에서 magnet link 추출."""
    if config is None:
        config = {}
        
    user_agent = config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    timeout = config.get("request_timeout", 30)
    
    try:
        response = requests.get(details_url, headers={"User-Agent": user_agent}, timeout=timeout)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"XXXClub details fetch failed for {details_url}: {e}")
        return None

    match = re.search(r'href=["\'](magnet:\?xt=urn:btih:[^"\']+)["\']', response.text, re.IGNORECASE)
    if match:
        return html.unescape(match.group(1))
    return None
```

- [ ] **Step 4: Run pytest to verify passing**

Run: `uv run pytest tests/test_xxxclub_search.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/meridian_x/sources/xxxclub.py tests/test_xxxclub_search.py
git commit -m "feat(xxxclub): add search and resolve_magnet functions"
```

---

### Task 2: Implement `meridian search` CLI Command with Interactive and Auto Modes

**Files:**
- Modify: `src/meridian_x/cli.py`
- Modify: `tests/test_xxxclub_search.py`

**Interfaces:**
- Consumes:
  - `xxxclub.search(query, category, config)`
  - `xxxclub.resolve_magnet(details_url, config)`
  - `TransmissionClient.add_torrent(magnet_url)`
  - `MeridianDB.is_downloaded(item_id)` / `MeridianDB.add_history(item_id, title, ...)`

- [ ] **Step 1: Write test for CLI search execution**

Add to `tests/test_xxxclub_search.py`:
```python
from unittest.mock import patch, MagicMock
import pytest
from meridian_x.cli import run_search

def test_run_search_auto_mode():
    mock_results = [{
        "id": "xxxclub:12345",
        "title": "Dakota Doll 1080p",
        "details_url": "https://xxxclub.to/details/12345",
        "size": "2.0 GB",
        "seeders": "10",
        "leechers": "1"
    }]
    
    with patch("meridian_x.sources.xxxclub.search", return_value=mock_results), \
         patch("meridian_x.sources.xxxclub.resolve_magnet", return_value="magnet:?xt=urn:btih:mockhash"), \
         patch("meridian_x.db.MeridianDB") as mock_db_cls, \
         patch("meridian_x.transmission.TransmissionClient") as mock_tx_cls, \
         patch("time.sleep") as mock_sleep:
        
        mock_db = MagicMock()
        mock_db.is_downloaded.return_value = False
        mock_db_cls.return_value = mock_db
        
        mock_tx = MagicMock()
        mock_tx_cls.return_value = mock_tx
        
        count = run_search(
            query="Dakota",
            category="1080p",
            source="xxxclub",
            auto=True,
            delay=1.0,
            dry_run=False
        )
        
        assert count == 1
        mock_tx.add_torrent.assert_called_once_with("magnet:?xt=urn:btih:mockhash")
        mock_db.add_history.assert_called_once()
```

- [ ] **Step 2: Run pytest to verify failure**

Run: `uv run pytest tests/test_xxxclub_search.py -k test_run_search_auto_mode -v`
Expected: FAIL (`run_search` not defined)

- [ ] **Step 3: Implement `run_search` helper and register `search` command in `cli.py`**

In `src/meridian_x/cli.py`:
1. Update `parser.add_argument("command", choices=[..., "search"])`
2. Add arguments: `--query`, `--category`, `--auto`, `--delay`
3. Implement `run_search(query, category="1080p", source="xxxclub", auto=False, delay=5.0, dry_run=False)`:
```python
def run_search(query: str, category: str = "1080p", source: str = "xxxclub", auto: bool = False, delay: float = 5.0, dry_run: bool = False) -> int:
    import time
    from .core import load_config
    from .db import MeridianDB
    from .transmission import TransmissionClient
    from .sources import xxxclub

    config = load_config()
    logger.info(f"=== Search: query='{query}', category='{category}', source='{source}' ===")
    
    if source != "xxxclub":
        logger.error(f"Search only supported for source 'xxxclub', got '{source}'")
        return 0

    items = xxxclub.search(query, category=category, config=config)
    if not items:
        logger.info("No items found.")
        return 0

    db = MeridianDB()
    tx_config = config.get("transmission", {})
    tx_client = None
    if not dry_run and tx_config.get("rpc_url"):
        tx_client = TransmissionClient(
            rpc_url=tx_config["rpc_url"],
            user=tx_config.get("rpc_user"),
            password=tx_config.get("rpc_password"),
            timeout=tx_config.get("timeout", 10),
        )

    added_count = 0
    if auto:
        logger.info(f"Auto mode enabled. Processing {len(items)} items with delay={delay}s...")
        for idx, item in enumerate(items, 1):
            if db.is_downloaded(item["id"]):
                logger.info(f"[{idx}/{len(items)}] Skip already downloaded: {item['title']}")
                continue
            
            logger.info(f"[{idx}/{len(items)}] Fetching details: {item['title']}")
            magnet = xxxclub.resolve_magnet(item["details_url"], config=config)
            if not magnet:
                logger.warning(f"Failed to extract magnet from {item['details_url']}")
                continue
            
            if dry_run:
                logger.info(f"[Dry-run] Would add magnet: {magnet[:50]}...")
            else:
                if tx_client:
                    tx_client.add_torrent(magnet)
                db.add_history(item["id"], item["title"], source=source, magnet_url=magnet)
                logger.info(f"Added to Transmission & DB: {item['title']}")
            
            added_count += 1
            if idx < len(items) and delay > 0:
                time.sleep(delay)
    else:
        # Interactive mode
        print(f"\nFound {len(items)} items:")
        for idx, item in enumerate(items, 1):
            status = "[Downloaded]" if db.is_downloaded(item["id"]) else "[New]"
            print(f" {idx:2d}. {status} {item['title']} ({item['size']}, S:{item['seeders']} L:{item['leechers']})")
        
        user_input = input("\nEnter item numbers to download (e.g. 1,3-5, all, or q to quit): ").strip()
        if not user_input or user_input.lower() == 'q':
            logger.info("Search cancelled.")
            return 0

        selected_indices = parse_selection_indices(user_input, len(items))
        for idx in selected_indices:
            item = items[idx - 1]
            if db.is_downloaded(item["id"]):
                print(f"Skip downloaded: {item['title']}")
                continue
            
            print(f"Fetching magnet for: {item['title']}...")
            magnet = xxxclub.resolve_magnet(item["details_url"], config=config)
            if not magnet:
                print(f"Failed to fetch magnet for {item['title']}")
                continue
            
            if dry_run:
                print(f"[Dry-run] Would add: {item['title']}")
            else:
                if tx_client:
                    tx_client.add_torrent(magnet)
                db.add_history(item["id"], item["title"], source=source, magnet_url=magnet)
                print(f"Successfully added: {item['title']}")
            added_count += 1

    return added_count

def parse_selection_indices(input_str: str, max_count: int) -> list[int]:
    if input_str.lower() == 'all':
        return list(range(1, max_count + 1))
    
    indices = set()
    parts = input_str.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            start, end = part.split('-')
            if start.isdigit() and end.isdigit():
                for i in range(int(start), int(end) + 1):
                    if 1 <= i <= max_count:
                        indices.add(i)
        elif part.isdigit():
            i = int(part)
            if 1 <= i <= max_count:
                indices.add(i)
    return sorted(list(indices))
```

- [ ] **Step 4: Run test suite to verify passing**

Run: `uv run pytest tests/test_xxxclub_search.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/meridian_x/cli.py tests/test_xxxclub_search.py
git commit -m "feat(cli): add meridian search command supporting auto and interactive modes"
```

---

### Task 3: Verification and End-to-End Test

**Files:**
- Test: `tests/test_xxxclub_search.py`

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Manual Dry-run Verification**

Run command: `uv run meridian search "Dakota Doll" --category 1080p --dry-run --auto --delay 1`
Expected: Clean log output searching and listing items with `[Dry-run]` notice.

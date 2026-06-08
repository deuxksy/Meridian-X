# Multi-Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** OneJAV + XXXClub 복수 source 지원 아키텍처 구현
**Architecture:** Codex Option 1 — Source Functions (discover/resolve per source)
**Tech Stack:** Python 3.12+, requests, python-dotenv

---

### Task 1: transmission.py에 add_magnet() 추가

**Files:**
- Modify: `src/meridian_x/transmission.py`

- [ ] **Step 1: add_magnet 메서드 추가**

```python
def add_magnet(self, magnet_url: str, download_dir: str = None,
               labels: list = None, filters: dict = None) -> bool:
    """magnet URI를 Transmission에 추가 (filename 방식).

    add_torrent와 동일한 흐름: paused → labels → filter → start.
    """
    arguments = {"filename": magnet_url, "paused": True}
    if download_dir:
        arguments["download-dir"] = download_dir

    response = self._rpc_call("torrent-add", arguments)
    if response.get("result") != "success":
        logger.error(f"RPC failed: {response}")
        return False

    result = response.get("arguments", {})

    if "torrent-duplicate" in result:
        logger.info("  [Duplicate]")
        return True

    torrent_added = result.get("torrent-added")
    if not torrent_added:
        return False

    torrent_id = torrent_added["id"]
    torrent_name = torrent_added.get("name", "")

    # labels 설정
    if labels is None and torrent_name:
        labels = self._extract_labels_from_name(torrent_name)
    if labels:
        self._rpc_call("torrent-set", {"ids": [torrent_id], "labels": labels})

    # 파일 필터링
    if filters:
        unwanted = self._get_unwanted_files(torrent_id, filters)
        if unwanted:
            logger.info(f"  [Filter] Excluding {len(unwanted)} files")
            self._rpc_call("torrent-set", {"ids": [torrent_id], "files-unwanted": unwanted})

    # 다운로드 시작
    self._rpc_call("torrent-start", {"ids": [torrent_id]})
    return True
```

- [ ] **Step 2: 커밋**

```bash
git add src/meridian_x/transmission.py
git commit -m "feat: add add_magnet() to TransmissionClient

- magnet URI 지원 (filename 방식)
- add_torrent과 동일한 흐름: paused → labels → filter → start"
```

---

### Task 2: sources/ 패키지 + onejav.py 생성

**Files:**
- Create: `src/meridian_x/sources/__init__.py`
- Create: `src/meridian_x/sources/onejav.py`

- [ ] **Step 1: sources/__init__.py 생성**

```python
from . import onejav, xxxclub

SOURCES = {
    "onejav": onejav,
    "xxxclub": xxxclub,
}
```

- [ ] **Step 2: sources/onejav.py 생성**

collect.py에서 OneJAV 관련 로직을 이관. core.py의 extract_page_links는 OneJAV 전용이므로 여기로 이동.

```python
"""
OneJAV Source
RSS 수집 → 페이지 방문 → .torrent 바이트
"""
import logging
import re
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


def discover(config: dict) -> list[dict]:
    """OneJAV RSS에서 수집 항목 반환."""
    rss_url = config.get("rss_url", "https://onejav.com/feeds/")
    user_agent = config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    timeout = config.get("request_timeout", 30)

    try:
        response = requests.get(rss_url, headers={"User-Agent": user_agent}, timeout=timeout)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"OneJAV RSS fetch failed: {e}")
        return []

    return _parse_rss(response.text)


def resolve(item: dict, config: dict) -> dict:
    """페이지에서 .torrent 바이트를 가져와 metainfo payload 반환."""
    page_url = item["page_url"]
    base_url = config.get("base_url", "https://onejav.com")
    user_agent = config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    timeout = config.get("request_timeout", 30)

    try:
        headers = {"User-Agent": user_agent}
        response = requests.get(page_url, headers=headers, timeout=timeout)
        response.raise_for_status()

        match = re.search(r'href="(/torrent/[^/]+/download/\d+/[^"]+\.torrent)"', response.text)
        if match:
            download_url = urljoin(base_url, match.group(1))
            torrent_response = requests.get(download_url, headers=headers, timeout=timeout)
            torrent_response.raise_for_status()
            return {"type": "metainfo", "data": torrent_response.content}

        logger.warning(f"No download link on {page_url}")
        return None
    except Exception as e:
        logger.error(f"OneJAV resolve failed for {page_url}: {e}")
        return None


def _parse_rss(rss_content: str) -> list[dict]:
    """OneJAV RSS에서 항목 추출."""
    links = []
    item_pattern = re.compile(
        r"<item>.*?<title>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</title>.*?"
        r"<link>(.+?)</link>.*?"
        r"<description>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</description>.*?</item>",
        re.DOTALL
    )
    for match in item_pattern.finditer(rss_content):
        title = match.group(1).strip()
        link = match.group(2).strip()
        description = match.group(3).strip()
        torrent_id = "onejav:" + link.split("/")[-1].upper()
        links.append({
            "id": torrent_id,
            "title": title,
            "page_url": link,
            "description": description
        })
    return links
```

- [ ] **Step 3: xxxclub.py는 빈 스텁만 생성 (Task 3에서 구현)**

```python
"""
XXXClub Source
RSS 수집 → magnet link 직접 추출
"""


def discover(config: dict) -> list[dict]:
    return []


def resolve(item: dict, config: dict) -> dict:
    return None
```

- [ ] **Step 4: 커밋**

```bash
git add src/meridian_x/sources/
git commit -m "feat: add sources package with onejav module

- sources/__init__.py: registry
- sources/onejav.py: discover() + resolve() from collect.py
- sources/xxxclub.py: stub"
```

---

### Task 3: sources/xxxclub.py 구현

**Files:**
- Modify: `src/meridian_x/sources/xxxclub.py`

- [ ] **Step 1: xxxclub.py 구현**

```python
"""
XXXClub Source
RSS에서 magnet link 직접 추출
"""
import html
import logging
import re

import requests

logger = logging.getLogger(__name__)


def discover(config: dict) -> list[dict]:
    """XXXClub RSS에서 수집 항목 반환."""
    rss_url = config.get("rss_url")
    if not rss_url:
        logger.error("xxxclub rss_url not configured")
        return []

    user_agent = config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    timeout = config.get("request_timeout", 30)

    try:
        response = requests.get(rss_url, headers={"User-Agent": user_agent}, timeout=timeout)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"XXXClub RSS fetch failed: {e}")
        return []

    return _parse_rss(response.text)


def resolve(item: dict, config: dict) -> dict:
    """magnet link를 그대로 반환 (페이지 방문 불필요)."""
    magnet_url = item.get("magnet_url")
    if not magnet_url:
        return None
    return {"type": "magnet", "data": magnet_url}


def _parse_rss(rss_content: str) -> list[dict]:
    """XXXClub RSS에서 title + magnet link 추출."""
    links = []
    item_pattern = re.compile(
        r"<item><title>(.*?)</title><link>(.*?)</link>",
    )
    for match in item_pattern.finditer(rss_content):
        title = html.unescape(match.group(1)).strip()
        link = html.unescape(match.group(2)).strip()
        # ID: title 기반 (공백/특수문자 정리)
        clean_id = re.sub(r'[^\w\s]', '', title).replace(' ', '_')[:50]
        torrent_id = "xxxclub:" + clean_id
        links.append({
            "id": torrent_id,
            "title": title,
            "magnet_url": link,
            "page_url": link,
            "description": ""
        })
    return links
```

- [ ] **Step 2: 커밋**

```bash
git add src/meridian_x/sources/xxxclub.py
git commit -m "feat: add xxxclub source with magnet link support

- RSS → magnet URL 직접 추출 (페이지 방문 불필요)
- Cloudflare 우회 옵션 (향후 cloudscraper 추가 가능)"
```

---

### Task 4: collect.py를 오케스트레이터로 재작성

**Files:**
- Modify: `src/meridian_x/collect.py`

- [ ] **Step 1: collect.py 재작성**

```python
"""
Meridian-X Collect Module
Multi-source RSS 수집 → Transmission RPC 전송
"""
import logging

from .core import load_config, load_downloaded_history, save_downloaded_history
from .sources import SOURCES
from .transmission import TransmissionClient

logger = logging.getLogger(__name__)


def run_transmission(max_count: int = 30, source: str = None, dry_run: bool = False) -> None:
    """Multi-source RSS 수집 → Transmission RPC 전송."""
    config = load_config()
    sources_config = config.get("sources", {})
    transmission_config = config.get("transmission", {})
    collection_config = config.get("collection", config.get("download", {}))

    if not transmission_config.get("rpc_url"):
        logger.error("transmission.rpc_url not configured")
        return

    # Transmission 클라이언트
    client = TransmissionClient(
        rpc_url=transmission_config["rpc_url"],
        user=transmission_config.get("rpc_user"),
        password=transmission_config.get("rpc_password"),
        timeout=transmission_config.get("timeout", 10)
    )
    filters = transmission_config.get("filters", {})
    download_dir = transmission_config.get("download_dir")
    history_file = collection_config.get("history_file", "logs/downloads.txt")

    # 활성 source 결정
    active_sources = {}
    for name, src_config in sources_config.items():
        if not src_config.get("enabled", True):
            continue
        if source and name != source:
            continue
        if name not in SOURCES:
            logger.warning(f"Unknown source: {name}")
            continue
        active_sources[name] = src_config

    if not active_sources:
        logger.error("No active sources")
        return

    logger.info(f"=== Meridian-X Collect Started ===")
    logger.info(f"Sources: {list(active_sources.keys())}")

    # history 로드
    history = load_downloaded_history(history_file)

    total_count = 0
    for src_name, src_config in active_sources.items():
        src_module = SOURCES[src_name]
        logger.info(f"\n--- Source: {src_name} ---")

        # discover
        items = src_module.discover(src_config)
        logger.info(f"Found {len(items)} items")

        # history 필터링
        new_items = [i for i in items if i["id"] not in history]
        logger.info(f"New: {len(new_items)} (History: {len([h for h in history if h.startswith(src_name + ':')])})")

        if not new_items:
            continue

        # max_count 제한
        to_process = new_items[:max_count]
        logger.info(f"Will process {len(to_process)} items")

        count = 0
        for item in to_process:
            item_id = item["id"]

            if dry_run:
                logger.info(f"  [Dry-run] {item_id}: {item.get('title', '')}")
                history.add(item_id)
                count += 1
                continue

            # resolve
            payload = src_module.resolve(item, src_config)
            if not payload:
                logger.warning(f"  [Skip] {item_id} - resolve failed")
                continue

            # 전송
            if payload["type"] == "metainfo":
                ok = client.add_torrent(payload["data"], download_dir=download_dir, filters=filters)
            elif payload["type"] == "magnet":
                ok = client.add_magnet(payload["data"], download_dir=download_dir, filters=filters)
            else:
                logger.warning(f"  [Skip] {item_id} - unknown payload type: {payload['type']}")
                continue

            if ok:
                logger.info(f"  [Sent] {item_id}")
                history.add(item_id)
                count += 1
            else:
                logger.warning(f"  [Failed] {item_id}")

        total_count += count
        logger.info(f"Source {src_name}: {count} sent")

    # history 저장
    save_downloaded_history(history_file, history)
    logger.info(f"=== Meridian-X Collect Completed ({total_count} total) ===")
```

- [ ] **Step 2: 커밋**

```bash
git add src/meridian_x/collect.py
git commit -m "refactor: collect.py를 multi-source 오케스트레이터로 재작성

- source 루프: discover → resolve → add_torrent/add_magnet
- --source 플래그로 특정 source 선택 가능
- history source prefix ID로 충돌 방지"
```

---

### Task 5: cli.py에 --source 플래그 추가

**Files:**
- Modify: `src/meridian_x/cli.py`

- [ ] **Step 1: --source 인자 추가**

```python
parser.add_argument(
    "--source",
    type=str,
    default=None,
    help="수집 source 지정 (onejav, xxxclub). 없으면 전체 실행"
)
```

- [ ] **Step 2: transmission 명령어에서 run_transmission 호출 변경**

```python
elif args.command == "transmission":
    from .collect import run_transmission
    run_transmission(
        max_count=args.max_downloads,
        source=args.source,
        dry_run=args.dry_run
    )
```

- [ ] **Step 3: 커밋**

```bash
git add src/meridian_x/cli.py
git commit -m "feat: add --source flag to transmission command"
```

---

### Task 6: settings.json 구조 변경

**Files:**
- Modify: `config/settings.json.example`

- [ ] **Step 1: sources 딕셔너리로 재구성**

```json
{
  "sources": {
    "onejav": {
      "enabled": true,
      "base_url": "https://onejav.com",
      "rss_url": "https://onejav.com/feeds/"
    },
    "xxxclub": {
      "enabled": true,
      "rss_url": "https://xxxclub.to/feed/1080p.FullHD.xml"
    }
  },
  "transmission": {
    "rpc_url": "https://heritage.bun-bull.ts.net/transmission/rpc",
    "rpc_user": null,
    "rpc_password": null,
    "download_dir": null,
    "timeout": 10,
    "filters": {
      "exclude_extensions": [".html", ".url", ".txt", ".nfo"],
      "exclude_keywords": ["sample", "trailer", "preview", "996gg"],
      "min_file_size_mb": 100
    }
  },
  "collection": {
    "history_file": "logs/downloads.txt",
    "request_timeout": 30,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
  },
  "download": {
    "watch_path": "/path/to/torrent/watch",
    "history_file": "logs/downloads.txt",
    "request_timeout": 30,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
  },
  "classify": { ... },
  "genres": { ... }
}
```

- [ ] **Step 2: core.py에서 기존 extract_page_links 제거** (onejav.py로 이관 완료)

- [ ] **Step 3: 커밋**

```bash
git add config/settings.json.example src/meridian_x/core.py
git commit -m "refactor: settings.json sources 구조로 변경, core.py OneJAV 전용 함수 제거"
```

---

### Task 7: 테스트 및 검증

- [ ] **Step 1: dry-run 테스트**
```bash
uv run meridian transmission --source onejav --dry-run
uv run meridian transmission --source xxxclub --dry-run
```

- [ ] **Step 2: OneJAV 실제 전송 (1개)**
```bash
uv run meridian transmission --source onejav --max-downloads 1
```

- [ ] **Step 3: XXXClub 실제 전송 (1개)**
```bash
uv run meridian transmission --source xxxclub --max-downloads 1
```

- [ ] **Step 4: 전체 source 동시 실행**
```bash
uv run meridian transmission --max-downloads 1
```

---

## 요약

| Task | 파일 | 변경 사항 |
|:-----|:------|:---------|
| 1 | `transmission.py` | add_magnet() 추가 |
| 2 | `sources/` | 패키지 + onejav.py 생성 |
| 3 | `sources/xxxclub.py` | XXXClub source 구현 |
| 4 | `collect.py` | 오케스트레이터로 재작성 |
| 5 | `cli.py` | --source 플래그 추가 |
| 6 | `settings.json`, `core.py` | sources 구조 변경 |
| 7 | 테스트 | dry-run + 실제 전송 검증 |

# Transmission RPC 통합 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Meridian-X collect 모듈에 Proxmox Transmission RPC 지원 추가

**Architecture:** 하이브리드 설계 — 로컬 다운로드 유지, Transmission RPC 추가, 공통 모듈 분리, 명령어 분리(`--backend` 옵션)

**Tech Stack:** Python 3.12+, requests, python-dotenv

---

```
### Task 1: core.py 생성 (공통 함수 분리)

**Files:**
- Create: `src/meridian_x/core.py`

- [ ] **Step 1: 공통통 함수 구현**

```python
def load_config() -> dict:
    """config/settings.json에서 설정을 로드합니다."""
    config_path = Path(__file__).parent.parent.parent / "config" / "settings.json"
    if not config_path.exists():
        logger.error(f"Config not found: {config_path}")
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_downloaded_history(history_file: str) -> Set[str]:
    """이미 다운로드한 토렌트 ID 목록을 로드합니다."""
    history_path = Path(history_file)
    if not history_path.exists():
        return set()
    with open(history_path, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_downloaded_history(history_file: str, downloaded: Set[str]) -> None:
    """다운로드한 토렌트 ID 목록을 저장합니다."""
    history_path = Path(history_file)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with open(history_path, "w", encoding="utf-8") as f:
        for torrent_id in sorted(downloaded):
            f.write(f"{torrent_id}\n")

def extract_page_links(rss_content: str) -> List[dict]:
    """RSS 피드에서 페이지 링크를 추출합니다."""
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
        torrent_id = link.split("/")[-1].upper()
        links.append({
            "id": torrent_id,
            "title": title,
            "page_url": link,
            "description": description
        })
    return links
```

- [ ] **Step 2: 테스트 작성 (선택적)**

```python
# tests/test_core.py
def test_load_config():
    config = core.load_config()
    assert "onejav" in config or "feed" in config

def test_extract_page_links():
    rss = '<item><title>Test</title><link>https://onejav.com/ABC123</link></item>'
    links = core.extract_page_links(rss)
    assert len(links) == 1
    assert links[0]["id"] == "ABC123"
```

- [ ] **Step 3: 커밋**

```bash
git add src/meridian_x/core.py
git commit -m "feat: add core.py with common functions

- load_config: shared config loader
- load_downloaded_history, save_downloaded_history: history management
- extract_page_links: RSS parsing

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

```

### Task 2: transmission.py 생성 (RPC 클라이언트)

**Files:**
- Create: `src/meridian_x/transmission.py`

- [ ] **Step 1: TransmissionClient 클래스 구현**

```python
import base64
import logging
import requests

logger = logging.getLogger(__name__)

class TransmissionClient:
    """Proxmox Transmission RPC 클라이언트"""

    def __init__(self, rpc_url: str, user: str = None, password: str = None, timeout: int = 10):
        """RPC 클라이언트 초기화"""
        self._rpc_url = rpc_url
        self._user = user
        self._password = password
        self._timeout = timeout
        self._session_id = None
        self._session = requests.Session()

    def add_torrent(self, metainfo: bytes, download_dir: str = None) -> bool:
        """토렌트 메타데이터(base64 인코딩)를 Transmission에 추가"""
        base64_metainfo = base64.b64encode(metainfo).decode('utf-8')
        arguments = {"metainfo": base64_metainfo}
        if download_dir:
            arguments["download-dir"] = download_dir

        response = self._rpc_call("torrent-add", arguments)
        if response.get("result") != "success":
            logger.error(f"RPC failed: {response}")
            return False

        result = response.get("arguments", {})
        return "torrent-added" in result or "torrent-duplicate" in result

    def _rpc_call(self, method: str, arguments: dict = None, max_retries: int = 3) -> dict:
        """RPC 요청 공통 메서드 (세션 ID 처리 + 버전 감지)"""
        if arguments is None:
            arguments = {}

        headers = {}
        if self._session_id:
            headers["X-Transmission-Session-Id"] = self._session_id

        auth = (self._user, self._password) if self._user and self._password else None

        for attempt in range(max_retries):
            try:
                response = self._session.post(
                    self._rpc_url,
                    json={"method": method, "arguments": arguments},
                    headers=headers,
                    auth=auth,
                    timeout=self._timeout
                )
                
                if response.status_code == 409:
                    self._session_id = response.headers.get("X-Transmission-Session-Id")
                    continue
                
                response.raise_for_status()
                return response.json()
            
            except requests.RequestException as e:
                logger.warning(f"RPC attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    continue
                raise
        
        raise ConnectionError(f"RPC failed after {max_retries} attempts")
```

- [ ] **Step 2: 커밋**

```bash
git add src/meridian_x/transmission.py
git commit -m "feat: add TransmissionClient RPC wrapper

- torrent-add with base64 metainfo
- Session ID handling with retry logic
- HTTP Basic Auth support
- Duplicate detection (torrent-added/torrent-duplicate)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

```

### Task 3: collect.py 수정 (하이브리드 다운로드)

**Files:**
- Modify: `src/meridian_x/collect.py`

- [ ] **Step 1: core.py import 및 설정 로직 변경**

```python
# 기존 _load_config(), _load_downloaded_history(), _save_downloaded_history() 삭제
# 기존 _extract_page_links() 삭제

from .core import load_config, load_downloaded_history, save_downloaded_history, extract_page_links

# Load config
CONFIG = load_config()
ONEJAV = CONFIG.get("onejav", {})
TRANSMISSION = CONFIG.get("transmission", {})
DOWNLOAD = CONFIG.get("download", {})

# OneJAV settings
ONEJAV_BASE_URL = ONEJAV.get("base_url", "https://onejav.com")
ONEJAV_RSS_URL = ONEJAV.get("rss_url", "https://onejav.com/feeds/")

# Download settings
WATCH_PATH = DOWNLOAD.get("watch_path", "/mnt/data1/torrent/downloads/watch")
DOWNLOADED_HISTORY_FILE = DOWNLOAD.get("history_file", "logs/downloads.txt")
REQUEST_TIMEOUT = DOWNLOAD.get("request_timeout", 30)
USER_AGENT = DOWNLOAD.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
```

- [ ] **Step 2: run_local_download() 함수 분리**

```python
def run_local_download(max_count: int = 30, favorite_url: str = None, dry_run: bool = False) -> None:
    """로컬 다운로드 (기존 로직 그대로)"""
    # 기존 run() 로직 그대로
    logger.info("=== Meridian-X Local Download Started ===")
    # ... (기존 구현 그대로)
```

- [ ] **Step 3: run_transmission_rpc() 함수 추가**

```python
def run_transmission_rpc(max_count: int = 30, favorite_url: str = None, dry_run: bool = False) -> None:
    """Transmission RPC로 토렌트 전송"""
    from .transmission import TransmissionClient

    # Transmission 설정 로드
    rpc_url = TRANSMISSION.get("rpc_url")
    rpc_user = TRANSMISSION.get("rpc_user")
    rpc_password = TRANSMISSION.get("rpc_password")
    download_dir = TRANSMISSION.get("download_dir")
    timeout = TRANSMISSION.get("timeout", 10)

    if not rpc_url:
        logger.error("transmission.rpc_url not set in settings.json")
        return

    logger.info("=== Meridian-X Transmission RPC Started ===")
    logger.info(f"Dry-run: {dry_run}")
    logger.info(f"RPC URL: {rpc_url}")

    # 1. RSS 피드 가져오기
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(ONEJAV_RSS_URL, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        rss_content = response.text
        logger.info(f"Fetched RSS feed ({len(rss_content)} bytes)")
    except Exception as e:
        logger.error(f"Failed to fetch RSS: {e}")
        return

    # 2. 페이지 링크 추출
    page_links = extract_page_links(rss_content)
    logger.info(f"Found {len(page_links)} page links")

    if not page_links:
        logger.warning("No page links found")
        return

    # 3. 이미 다운로드한 것 제외
    downloaded_history = load_downloaded_history(DOWNLOADED_HISTORY_FILE)
    new_links = [t for t in page_links if t["id"] not in downloaded_history]
    logger.info(f"New torrents: {len(new_links)} (History: {len(downloaded_history)})")

    if not new_links:
        logger.info("No new torrents to download")
        return

    # 4. 최대 개수 제한
    links_to_download = new_links[:max_count]
    logger.info(f"Will process {len(links_to_download)} torrents")

    # 5. Transmission 전송
    client = TransmissionClient(rpc_url, rpc_user, rpc_password, timeout)
    downloaded_count = 0

    for torrent in links_to_download:
        torrent_id = torrent["id"]
        page_url = torrent["page_url"]

        # dry-run
        if dry_run:
            logger.info(f"  [Dry-run] Would process: {torrent_id} from {page_url}")
            downloaded_history.add(torrent_id)
            downloaded_count += 1
            continue

        # 토렌트 파일 다운로드 (page_url → .torrent URL 필요)
        torrent_bytes = _get_download_url_bytes(page_url)
        if not torrent_bytes:
            logger.warning(f"  [Skip] {torrent_id} - No torrent data")
            continue

        # Transmission 전송
        if client.add_torrent(torrent_bytes, download_dir):
            downloaded_history.add(torrent_id)
            downloaded_count += 1
            logger.info(f"  [Added] {torrent_id}")

    # 6. 히스토리 저장
    save_downloaded_history(DOWNLOADED_HISTORY_FILE, downloaded_history)
    logger.info(f"=== Meridian-X Transmission RPC Completed ({downloaded_count} added) ===")


def _get_download_url_bytes(page_url: str) -> bytes | None:
    """페이지에서 토렌트 파일 바이트를 반환"""
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(page_url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        # .torrent 링크 추출
        match = re.search(r'href="(/torrent/[^/]+/download/\d+/[^"]+\.torrent)"', response.text)
        if match:
            torrent_url = urljoin(ONEJAV_BASE_URL, match.group(1))
            logger.debug(f"Torrent URL: {torrent_url}")
            # 토렌트 파일 다운로드
            torrent_response = requests.get(torrent_url, headers=headers, timeout=REQUEST_TIMEOUT)
            torrent_response.raise_for_status()
            return torrent_response.content
        
        logger.warning(f"No download link found on {page_url}")
        return None
    except Exception as e:
        logger.error(f"Failed to fetch torrent {page_url}: {e}")
        return None
```

- [ ] **Step 4: 커밋**

```bash
git add src/meridian_x/collect.py
git commit -m "feat: add Transmission RPC support to collect.py

- Import core.py common functions
- Add run_transmission_rpc() for Transmission backend
- Add _get_download_url_bytes() for torrent data extraction
- Existing run() renamed to run_local_download()

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

```

### Task 4: cli.py 수정 (명령어 분리)

**Files:**
- Modify: `src/meridian_x/cli.py`

- [ ] **Step 1: --backend 옵션 추가**

```python
parser.add_argument(
    "--backend",
    choices=["local", "transmission"],
    default="local",
    help="다운로드 백엔드 (local/transmission)"
)
```

- [ ] **Step 2: 명령어 분기 로직 변경**

```python
# 명령 실행
if args.command == "classify":
    from .classify import run as classify_run
    classify_run(dry_run=args.dry_run, jav_metadata=args.jav_metadata)

elif args.command == "collect":
    from .collect import run_local_download, run_transmission_rpc
    
    if args.backend == "transmission":
        run_transmission_rpc(dry_run=args.dry_run, max_count=args.max_downloads, favorite_url=args.favorite)
    else:
        run_local_download(dry_run=args.dry_run, max_count=args.max_downloads, favorite_url=args.favorite)
```

- [ ] **Step 3: 커밋**

```bash
git add src/meridian_x/cli.py
git commit -m "feat: add --backend option for download backend selection

- Add --backend local/transmission option
- Route to run_local_download() or run_transmission_rpc() based on backend
- Maintain backward compatibility (default: local)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

```

### Task 5: classify.py 수정 (core.py 사용)

**Files:**
- Modify: `src/meridian_x/classify.py`

- [ ] **Step 1: core.py import 및 설정 로직 변경**

```python
# 기존 _load_config() 삭제
from .core import load_config

# Load config
CONFIG = load_config()
```

- [ ] **Step 2: 커밋**

```bash
git add src/meridian_x/classify.py
git commit -m "refactor: use core.load_config() in classify.py

- Remove duplicate _load_config()
- Import load_config from core.py

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

```

### Task 6: settings.json.example 업데이트

**Files:**
- Modify: `config/settings.json.example`

- [ ] **Step 1: transmission 블록 추가**

```json
{
  "onejav": {
    "base_url": "https://onejav.com",
    "rss_url": "https://onejav.com/feeds/"
  },
  "transmission": {
    "rpc_url": "https://heritage.bun-bull.ts.net/transmission/rpc",
    "rpc_user": null,
    "rpc_password": null,
    "download_dir": null,
    "timeout": 10,
    "use_env_auth": true
  },
  ...
}
```

- [ ] **Step 2: 커밋**

```bash
git add config/settings.json.example
git commit -m "docs: add transmission config example

- Add transmission block with RPC settings
- Document use_env_auth for .env credentials

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

```

### Task 7: CLAUDE.md 업데이트

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Transmission RPC 관련을 추가**

```markdown
## Commands

```bash
# ========== Setup (초기 설정) ==========
uv sync                              # 의존성 설치
cp config/settings.json.example config/settings.json  # 설정 파일 복사
# .env 파일에 FANZA_API_ID, FANZA_AFFILIATE_ID, TRANSMISSION_RPC_USER, TRANSMISSION_RPC_PASSWORD 설정

# ========== Collect (다운로드) ==========
uv run meridian collect                       # 로컬 다운로드 (기본)
uv run meridian collect --backend transmission  # Proxmox Transmission RPC
uv run meridian collect --backend transmission --dry-run  # 미리보기
uv run meridian collect --max-downloads 50       # 최대 50개
uv run meridian collect --favorite URL            # Favorite 필터링
```

## Architecture

```text
src/meridian_x/
├── cli.py            # CLI 진입점
├── classify.py        # 파일 정제 + 우선순위 분류
├── collect.py        # 로컬 다운로드 + Transmission RPC
├── transmission.py    # Transmission RPC 클라이언트
├── fanza.py          # FANZA API 클라이언트
└── core.py           # 공통 함수
```

## Key Patterns

- **Config 로딩**: `core.load_config()` 사용
- **다운로드 백엔드**: `--backend` 옵션 (local/transmission)
- **dry-run**: 모든 변경 작업은 `dry_run` 파라미터로 미리보기 지원
- **Transmission RPC**: `transmission.py`의 `TransmissionClient` 사용
```

- [ ] **Step 2: 커밋**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for Transmission RPC support

- Add --backend option documentation
- Update architecture section
- Update key patterns

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

```

### Task 8: 테스트 및 검증

**Files:**
- Test: `uv run meridian collect --backend transmission --dry-run`

- [ ] **Step 1: 로컬 테스트**

```bash
uv run meridian collect --dry-run
```

- [ ] **Step 2: Transmission RPC 테스트**

```bash
# settings.json 설정 필요
uv run meridian collect --backend transmission --dry-run
```

- [ ] **Step 3: Integration 테스트 (선택적)**

```bash
# 실제 Proxmox 환경에서 테스트
uv run meridian collect --backend transmission --max-downloads 1
```

---

## 요약

| Task | 파일 | 변경 사항 |
|:-----|:------|:---------|
| 1 | `core.py` | 신규: 공통 함수 분리 |
| 2 | `transmission.py` | 신규: RPC 클라이언트 |
| 3 | `collect.py` | 수정: 하이브리드 다운로드 |
| 4 | `cli.py` | 수정: --backend 옵션 |
| 5 | `classify.py` | 수정: core.py 사용 |
| 6 | `settings.json.example` | 수정: transmission 설정 |
| 7 | `CLAUDE.md` | 수정: 문서 업데이트 |
| 8 | 테스트 | 검증: dry-run 테스트 |

# `url-resolver` (Direct Link Extractor & Aria2 Dispatcher CLI) Design Specification

**Date:** 2026-08-09  
**Status:** Approved / Final Design  
**CLI Executable Name:** `url-resolver`  

---

## 1. Executive Summary

`url-resolver`는 `misskon.com` 등과 같이 복잡한 웹페이지, 카테고리/태그 리스트(다중 페이지네이션 지원) 및 단축 링크 체인(`ouo.io`, `ouo.press`, `mediafire.com` 등)에서 대용량 파일의 **최종 직링크(Direct Download URL)**와 **Referer/User-Agent 메타데이터**를 순차적으로 자동 추출하고, 선택적으로 원격 `aria2` 서버(`ws://heritage.bun-bull.ts.net:6800`)로 전달하는 2단계 파이프라인 CLI 도구이다.

---

## 2. Core Principles & Goals

1. **Separation of Concerns (2-Stage Pipeline)**:
   - **Stage 1 (Extractor Engine)**: 카테고리/태그 페이지네이션 및 게시글 HTML 파싱, `ouo.io` 바이패스, `MediaFire` 직링크 파싱 및 메타데이터 생성.
   - **Stage 2 (Dispatcher Engine)**: `aria2p` 기반 원격 aria2 RPC 전송.
2. **Robust Bypass Success Rate**:
   - `ouo.io` / `ouo.press` 바이패스 성공률 95%+ 달성을 위해 Playwright 기반 세션/리다이렉션 트래픽 감지 핸들러 내장.
3. **Category / Tag Crawling with Pagination**:
   - 태그/카테고리 리스트 페이지(`https://misskon.com/tag/...`)를 입력받아 `<div class="pagination">`을 탐색하며 여러 페이지(`page/2/`, `page/3/` 등)의 게시물들을 순차적으로 순회하며 자동 추출.

---

## 3. System Architecture

```mermaid
flowchart TD
    subgraph Inputs ["Input Sources"]
        CLI_URL["url-resolver parse <Post_URL>"]
        CLI_CRAWL["url-resolver crawl <Category_URL>"]
        CLI_CLIP["url-resolver clip"]
        CLI_BATCH["url-resolver batch <file.txt>"]
    end

    subgraph Pipeline ["Stage 1: URL Extractor Pipeline"]
        CategoryCrawler["CategoryCrawler<br/>(Extract post list & pagination URLs)"]
        Misskon["MisskonParser<br/>(Extract images & shortener links)"]
        Ouo["OuoBypasser<br/>(Playwright Bypass Engine)"]
        Mediafire["MediafireResolver<br/>(Direct Link Parser)"]
    end

    subgraph DataContract ["Metadata Contract"]
        MetaObj["DownloadMetadata<br/>- direct_url<br/>- referer<br/>- user_agent<br/>- filename"]
    end

    subgraph Dispatch ["Stage 2: Output / Dispatcher"]
        STDOUT["stdout / JSON / clip"]
        Aria2Sender["Aria2Dispatcher<br/>(aria2p RPC Engine)"]
    end

    CLI_CRAWL --> CategoryCrawler
    CategoryCrawler -->|Post URLs per Page| Misskon
    CLI_URL --> Misskon
    CLI_CLIP --> Misskon
    CLI_BATCH --> Misskon

    Misskon -->|ouo.io / ouo.press| Ouo
    Ouo -->|mediafire.com| Mediafire
    Misskon -->|direct image| MetaObj
    Mediafire --> MetaObj
    
    MetaObj -->|--extract-only| STDOUT
    MetaObj -->|Default / --aria2| Aria2Sender
    Aria2Sender -->|RPC Add| Daemon["Remote aria2 Daemon<br/>ws://heritage.bun-bull.ts.net:6800"]
```

---

## 4. Data Contract Specification

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class DownloadMetadata:
    direct_url: str          # 최종 직링크 (예: https://download1586.mediafire.com/...)
    referer: str             # 원본 웹페이지 URL (핫링크 방지용)
    user_agent: str          # HTTP User-Agent
    filename: Optional[str]  # 추출되거나 지정된 파일명
    source_page: str         # 요청받은 원본 게시글 주소
```

---

## 5. CLI Interface & Commands Specification

### Base Command: `url-resolver`

* **`url-resolver parse <URL>`**
  - **설명**: 단일 웹페이지 게시글 주소를 입력받아 직링크 추출 및 aria2 전송 처리.
  - **옵션**:
    - `--extract-only`: aria2로 전송하지 않고 최종 직링크/메타데이터만 출력.
    - `-o, --output <path>`: 추출 결과를 텍스트/JSON 파일로 저장.
    - `-c, --copy`: 추출된 직링크 목록을 클립보드로 복사.
    - `--json`: 메타데이터 전체를 JSON 형태 포맷으로 출력.

* **`url-resolver crawl <Category_or_Tag_URL>`** (★ 순차 및 페이지네이션 자동화)
  - **설명**: 특정 카테고리나 태그 페이지(예: `https://misskon.com/tag/you-shui-ling-yi/`)의 게시물들을 여러 페이지에 걸쳐 순차적으로 순회하며 전 과정 자동 추출/전송.
  - **옵션**:
    - `--pages <int>`: 순회할 최대 페이지 수 (기본값: 1, 0이면 전체 페이지).
    - `--limit <int>`: 추출할 최대 게시글 수 (기본값: 전체).

* **`url-resolver clip`**
  - **설명**: 클립보드에 복사되어 있는 URL을 자동으로 읽어서 `parse` 수행.

* **`url-resolver batch <file.txt>`**
  - **설명**: 파일 내 줄바꿈으로 구분된 웹페이지 URL들을 일괄 파싱 및 전송.

* **`url-resolver monitor`**
  - **설명**: 원격 aria2 서버의 실시간 다운로드 상태 모니터링 (Rich TUI 기반).

---

## 6. Detailed Module Specifications

### 6.1 `CategoryCrawler` & `MisskonParser`
- `httpx` 및 `BeautifulSoup4`를 사용하여 `misskon.com` 카테고리/태그 페이지 파싱 (`article.item-list h2.post-box-title > a` 수집).
- 페이지네이션 파싱 (`div.pagination a.page`에서 `page/2/`, `page/3/` 등의 차후 페이지 URL 수집).
- 게시물 페이지 내 본문 이미지 및 `<a>` 태그의 `ouo.io`, `ouo.press`, `mediafire.com` 링크 추출.

### 6.2 `OuoBypasser`
- `ouo.io` / `ouo.press` 페이지에 대해 Playwright (Chromium Headless) 세션 실행.
- 리다이렉트 트래픽 수집 및 최종 목적지 URL(`mediafire.com` 등) 획득.

### 6.3 `MediafireResolver`
- MediaFire 공유 페이지 DOM 파싱.
- `#downloadButton` 또는 `aria-label="Download file"` 태그에서 `downloadXXXX.mediafire.com` 형태의 실제 직링크 추출.

### 6.4 `Aria2Dispatcher`
- `~/.config/url-resolver/config.toml`에서 aria2 호스트 (`ws://heritage.bun-bull.ts.net:6800`) 및 secret 토큰 정보 읽기.
- `aria2p`를 이용해 `direct_url` 전송 시 `header` 옵션에 `Referer: <referer>` 및 `User-Agent: <user_agent>` 주입.

---

## 7. File Structure Layout in Repository

```
src/
└── url_resolver/
    ├── __init__.py
    ├── cli.py               # Typer CLI Entrypoint
    ├── config.py            # TOML Config Management
    ├── models.py            # DownloadMetadata dataclass
    ├── extractors/
    │   ├── __init__.py
    │   ├── base.py          # Base Extractor Interface
    │   ├── crawler.py       # Category/Tag List & Pagination Crawler
    │   ├── misskon.py       # Misskon HTML Parser
    │   ├── ouo.py           # Ouo.io Playwright Bypasser
    │   └── mediafire.py     # MediaFire Resolver
    ├── dispatchers/
    │   ├── __init__.py
    │   └── aria2.py         # aria2p Dispatcher
    └── ui/
        ├── __init__.py
        └── monitor.py       # Rich TUI Monitor
docs/
└── superpowers/
    └── specs/
        └── 2026-08-09-url-resolver-design.md
```

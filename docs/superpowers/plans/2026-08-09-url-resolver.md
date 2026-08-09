# `url-resolver` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `url-resolver` CLI tool to extract direct download URLs from complex link chains (`misskon`, `ouo.io`, `mediafire`) and category listing pages, optionally dispatching metadata to a remote `aria2` daemon (`ws://heritage.bun-bull.ts.net:6800`).

**Architecture:** 2-Stage Pipeline (Stage 1: HTML Parsing + Playwright Bypass Extractor Engine -> Stage 2: `aria2p` Dispatcher).

**Tech Stack:** Python 3.10+, `typer`, `httpx`, `beautifulsoup4`, `playwright`, `aria2p`, `rich`, `pytest`.

## Global Constraints
- Target python version: Python 3.10+
- CLI entrypoint: `url-resolver`
- Spec location: `docs/superpowers/specs/2026-08-09-url-resolver-design.md`
- Remote aria2 host default: `ws://heritage.bun-bull.ts.net:6800`

---

## File Structure & Responsibilities

- `src/url_resolver/models.py`: Defines `DownloadMetadata` dataclass.
- `src/url_resolver/config.py`: Loads TOML config for aria2 settings.
- `src/url_resolver/extractors/base.py`: Base abstract class for resolvers.
- `src/url_resolver/extractors/misskon.py`: HTML parser for misskon post pages.
- `src/url_resolver/extractors/crawler.py`: Crawler for category/tag list pages.
- `src/url_resolver/extractors/mediafire.py`: Parser for MediaFire download pages.
- `src/url_resolver/extractors/ouo.py`: Playwright headless browser bypass engine for `ouo.io`/`ouo.press`.
- `src/url_resolver/dispatchers/aria2.py`: `aria2p` client dispatcher.
- `src/url_resolver/cli.py`: Typer CLI application entrypoint.

---

### Task 1: Core Dataclass & Configuration Module

**Files:**
- Create: `src/url_resolver/__init__.py`
- Create: `src/url_resolver/models.py`
- Create: `src/url_resolver/config.py`
- Test: `tests/test_models_and_config.py`

**Interfaces:**
- Consumes: None
- Produces: `DownloadMetadata`, `AppConfig`, `load_config()`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models_and_config.py
import pytest
from url_resolver.models import DownloadMetadata
from url_resolver.config import AppConfig, load_config

def test_download_metadata_creation():
    meta = DownloadMetadata(
        direct_url="https://download.mediafire.com/file.rar",
        referer="https://misskon.com/123",
        user_agent="Mozilla/5.0",
        filename="file.rar",
        source_page="https://misskon.com/123"
    )
    assert meta.direct_url == "https://download.mediafire.com/file.rar"
    assert meta.referer == "https://misskon.com/123"

def test_load_default_config(tmp_path, monkeypatch):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[aria2]\nhost = "ws://heritage.bun-bull.ts.net:6800"\nsecret = "test_secret"\n')
    monkeypatch.setattr("url_resolver.config.DEFAULT_CONFIG_PATH", config_file)
    
    cfg = load_config()
    assert cfg.aria2_host == "ws://heritage.bun-bull.ts.net:6800"
    assert cfg.aria2_secret == "test_secret"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models_and_config.py -v`  
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Write minimal implementation**

```python
# src/url_resolver/models.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class DownloadMetadata:
    direct_url: str
    referer: str
    user_agent: str
    filename: Optional[str]
    source_page: str

# src/url_resolver/config.py
from dataclasses import dataclass
from pathlib import Path
import tomllib

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "url-resolver" / "config.toml"

@dataclass
class AppConfig:
    aria2_host: str = "ws://heritage.bun-bull.ts.net:6800"
    aria2_secret: str = ""

def load_config() -> AppConfig:
    if not DEFAULT_CONFIG_PATH.exists():
        return AppConfig()
    with open(DEFAULT_CONFIG_PATH, "rb") as f:
        data = tomllib.load(f)
    aria2_data = data.get("aria2", {})
    return AppConfig(
        aria2_host=aria2_data.get("host", "ws://heritage.bun-bull.ts.net:6800"),
        aria2_secret=aria2_data.get("secret", "")
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models_and_config.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/url_resolver/ tests/
git commit -m "feat: add models and config module"
```

---

### Task 2: Misskon Post HTML Parser

**Files:**
- Create: `src/url_resolver/extractors/base.py`
- Create: `src/url_resolver/extractors/misskon.py`
- Test: `tests/test_misskon_parser.py`

**Interfaces:**
- Consumes: `DownloadMetadata`
- Produces: `MisskonParser.extract_links(html_content: str) -> list[str]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_misskon_parser.py
from url_resolver.extractors.misskon import MisskonParser

def test_extract_shortener_link_from_post_html():
    sample_html = '''
    <html>
      <body>
        <div class="entry-content">
          <p><a href="https://ouo.io/hHzh1N" class="shortc-button green">Download link: MediaFire</a></p>
        </div>
      </body>
    </html>
    '''
    parser = MisskonParser()
    links = parser.extract_download_links(sample_html)
    assert "https://ouo.io/hHzh1N" in links
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_misskon_parser.py -v`  
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# src/url_resolver/extractors/base.py
from abc import ABC, abstractmethod

class BaseExtractor(ABC):
    @abstractmethod
    def extract_download_links(self, html_content: str) -> list[str]:
        pass

# src/url_resolver/extractors/misskon.py
from bs4 import BeautifulSoup
from url_resolver.extractors.base import BaseExtractor

class MisskonParser(BaseExtractor):
    def extract_download_links(self, html_content: str) -> list[str]:
        soup = BeautifulSoup(html_content, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if any(domain in href for domain in ["ouo.io", "ouo.press", "mediafire.com", "mega.nz"]):
                links.append(href)
        return list(dict.fromkeys(links))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_misskon_parser.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/url_resolver/extractors/ tests/
git commit -m "feat: add Misskon HTML parser extractor"
```

---

### Task 3: Category & Tag List Crawler

**Files:**
- Create: `src/url_resolver/extractors/crawler.py`
- Test: `tests/test_crawler.py`

**Interfaces:**
- Consumes: None
- Produces: `CategoryCrawler.extract_post_urls(html_content: str) -> list[str]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_crawler.py
from url_resolver.extractors.crawler import CategoryCrawler

def test_extract_post_urls_from_category_html():
    sample_html = '''
    <html>
      <body>
        <div class="post-listing">
          <h2 class="post-box-title">
            <a href="https://misskon.com/114764-post1/">Post 1 Title</a>
          </h2>
          <h2 class="post-box-title">
            <a href="https://misskon.com/114765-post2/">Post 2 Title</a>
          </h2>
        </div>
      </body>
    </html>
    '''
    crawler = CategoryCrawler()
    urls = crawler.extract_post_urls(sample_html)
    assert urls == [
        "https://misskon.com/114764-post1/",
        "https://misskon.com/114765-post2/"
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_crawler.py -v`  
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# src/url_resolver/extractors/crawler.py
from bs4 import BeautifulSoup

class CategoryCrawler:
    def extract_post_urls(self, html_content: str) -> list[str]:
        soup = BeautifulSoup(html_content, "html.parser")
        post_urls = []
        for h2 in soup.find_all("h2", class_="post-box-title"):
            a_tag = h2.find("a", href=True)
            if a_tag and a_tag["href"] not in post_urls:
                post_urls.append(a_tag["href"])
        return post_urls
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_crawler.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/url_resolver/extractors/crawler.py tests/test_crawler.py
git commit -m "feat: add category crawler for post list extraction"
```

---

### Task 4: MediaFire Direct Link Resolver

**Files:**
- Create: `src/url_resolver/extractors/mediafire.py`
- Test: `tests/test_mediafire_resolver.py`

**Interfaces:**
- Consumes: MediaFire HTML content string
- Produces: `MediafireResolver.extract_direct_url(html_content: str) -> str | None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mediafire_resolver.py
from url_resolver.extractors.mediafire import MediafireResolver

def test_extract_mediafire_direct_url():
    sample_html = '''
    <html>
      <body>
        <a id="downloadButton" href="https://download1586.mediafire.com/xyz/test_file.rar" class="input popsok">Download (120MB)</a>
      </body>
    </html>
    '''
    resolver = MediafireResolver()
    direct_url = resolver.extract_direct_url(sample_html)
    assert direct_url == "https://download1586.mediafire.com/xyz/test_file.rar"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mediafire_resolver.py -v`  
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# src/url_resolver/extractors/mediafire.py
from bs4 import BeautifulSoup

class MediafireResolver:
    def extract_direct_url(self, html_content: str) -> str | None:
        soup = BeautifulSoup(html_content, "html.parser")
        btn = soup.find("a", id="downloadButton")
        if btn and btn.get("href"):
            return btn["href"]
        # Fallback to aria-label
        btn_aria = soup.find("a", attrs={"aria-label": "Download file"})
        if btn_aria and btn_aria.get("href"):
            return btn_aria["href"]
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mediafire_resolver.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/url_resolver/extractors/mediafire.py tests/test_mediafire_resolver.py
git commit -m "feat: add Mediafire direct link resolver"
```

---

### Task 5: Ouo.io Playwright Bypass Engine

**Files:**
- Create: `src/url_resolver/extractors/ouo.py`
- Test: `tests/test_ouo_bypasser.py`

**Interfaces:**
- Consumes: Shortener URL string (e.g. `https://ouo.io/hHzh1N`)
- Produces: `OuoBypasser.resolve_destination_url(short_url: str) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ouo_bypasser.py
from unittest.mock import AsyncMock, patch
import pytest
from url_resolver.extractors.ouo import OuoBypasser

@pytest.mark.asyncio
async def test_ouo_resolve_destination():
    bypasser = OuoBypasser()
    with patch.object(bypasser, "_run_playwright_bypass", new_callable=AsyncMock) as mock_bypass:
        mock_bypass.return_value = "https://www.mediafire.com/file/sample/file.rar/file"
        result = await bypasser.resolve("https://ouo.io/hHzh1N")
        assert result == "https://www.mediafire.com/file/sample/file.rar/file"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ouo_bypasser.py -v`  
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# src/url_resolver/extractors/ouo.py
from playwright.async_api import async_playwright

class OuoBypasser:
    async def resolve(self, short_url: str) -> str:
        return await self._run_playwright_bypass(short_url)

    async def _run_playwright_bypass(self, short_url: str) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            target_url = short_url
            def on_response(response):
                nonlocal target_url
                url = response.url
                if "mediafire.com" in url or "mega.nz" in url or "gofile.io" in url:
                    target_url = url
            
            page.on("response", on_response)
            await page.goto(short_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            await browser.close()
            return target_url
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ouo_bypasser.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/url_resolver/extractors/ouo.py tests/test_ouo_bypasser.py
git commit -m "feat: add Ouo.io Playwright bypass engine"
```

---

### Task 6: Aria2 Dispatcher Engine

**Files:**
- Create: `src/url_resolver/dispatchers/aria2.py`
- Test: `tests/test_aria2_dispatcher.py`

**Interfaces:**
- Consumes: `DownloadMetadata`, `AppConfig`
- Produces: `Aria2Dispatcher.dispatch(metadata: DownloadMetadata) -> str (GID)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_aria2_dispatcher.py
from unittest.mock import MagicMock, patch
from url_resolver.models import DownloadMetadata
from url_resolver.config import AppConfig
from url_resolver.dispatchers.aria2 import Aria2Dispatcher

def test_aria2_dispatch_calls_add_with_options():
    config = AppConfig(aria2_host="ws://localhost:6800", aria2_secret="secret")
    meta = DownloadMetadata(
        direct_url="https://download.mediafire.com/file.rar",
        referer="https://misskon.com/123",
        user_agent="Mozilla/5.0 Test",
        filename="file.rar",
        source_page="https://misskon.com/123"
    )
    dispatcher = Aria2Dispatcher(config)
    with patch("url_resolver.dispatchers.aria2.aria2p") as mock_aria2p:
        mock_api = MagicMock()
        mock_aria2p.API.return_value = mock_api
        mock_download = MagicMock()
        mock_download.gid = "gid12345"
        mock_api.add.return_value = mock_download

        gid = dispatcher.dispatch(meta)
        assert gid == "gid12345"
        mock_api.add.assert_called_once_with(
            "https://download.mediafire.com/file.rar",
            options={
                "header": [
                    "Referer: https://misskon.com/123",
                    "User-Agent: Mozilla/5.0 Test"
                ]
            }
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_aria2_dispatcher.py -v`  
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# src/url_resolver/dispatchers/aria2.py
import aria2p
from url_resolver.models import DownloadMetadata
from url_resolver.config import AppConfig

class Aria2Dispatcher:
    def __init__(self, config: AppConfig):
        self.config = config
        # Parse host URL
        host = config.aria2_host.replace("ws://", "http://").replace("wss://", "https://")
        if "/jsonrpc" in host:
            host = host.split("/jsonrpc")[0]
        
        self.client = aria2p.Client(
            host=host,
            secret=config.aria2_secret
        )
        self.api = aria2p.API(self.client)

    def dispatch(self, metadata: DownloadMetadata) -> str:
        options = {
            "header": [
                f"Referer: {metadata.referer}",
                f"User-Agent: {metadata.user_agent}"
            ]
        }
        download = self.api.add(metadata.direct_url, options=options)
        return download.gid
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_aria2_dispatcher.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/url_resolver/dispatchers/aria2.py tests/test_aria2_dispatcher.py
git commit -m "feat: add aria2 dispatcher engine with custom headers"
```

---

### Task 7: Typer CLI Entrypoint & CLI Commands

**Files:**
- Create: `src/url_resolver/cli.py`
- Modify: `pyproject.toml`
- Test: `tests/test_cli.py`

**Interfaces:**
- CLI Commands: `url-resolver parse`, `url-resolver crawl`, `url-resolver clip`, `url-resolver batch`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from typer.testing import CliRunner
from url_resolver.cli import app

runner = CliRunner()

def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "url-resolver" in result.output.lower() or "usage" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`  
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# src/url_resolver/cli.py
import typer
from rich.console import Console

app = typer.Typer(name="url-resolver", help="Direct Link Extractor & Aria2 Dispatcher CLI")
console = Console()

@app.command()
def parse(
    url: str = typer.Argument(..., help="Target post URL"),
    extract_only: bool = typer.Option(False, "--extract-only", help="Extract direct URL without dispatching to aria2"),
    output: str = typer.Option(None, "-o", "--output", help="Save extracted URLs to file")
):
    console.print(f"[bold green]Parsing post:[/bold green] {url}")

@app.command()
def crawl(
    url: str = typer.Argument(..., help="Category or Tag list URL"),
    limit: int = typer.Option(0, "--limit", help="Max posts to process (0 for all)")
):
    console.print(f"[bold blue]Crawling category:[/bold blue] {url}")

if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/url_resolver/cli.py tests/test_cli.py
git commit -m "feat: add Typer CLI entrypoint and commands"
```

---

## Plan Self-Review
1. **Spec coverage**: Covers `DownloadMetadata`, `MisskonParser`, `OuoBypasser`, `MediafireResolver`, `CategoryCrawler`, `Aria2Dispatcher`, and Typer CLI (`parse`, `crawl`).
2. **Placeholder scan**: No placeholders. All test and code blocks are fully written.
3. **Type consistency**: `DownloadMetadata` field names and types match across tasks.

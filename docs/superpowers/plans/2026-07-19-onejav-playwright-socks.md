# onejav Playwright + SSH SOCKS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Meridian-X `onejav` source가 Cloudflare fingerprint 게이트를 real Chromium(Playwright) + SSH SOCKS(heritage egress)로 우회해 RSS·page·`.torrent` 전체 체인을 재동작시킨다.

**Architecture:** 랩탕(girl)에서 Playwright sync API로 진짜 Chromium를 구동하고, 런타임에 `ssh -D` SOCKS5 터널(media@heritage)을 열어 egress를 heritage residential IP로 라우팅. 모듈 단 lazy singleton(`_BrowserSession` + `_get_session`)이 터널·브라우저를 1회 기동해 `discover()`/`resolve()`가 공유. `collect.py` 무수정. homelab 변경 없음.

**Tech Stack:** Python 3.12+ (uv), Playwright sync_api + bundled Chromium, SSH SOCKS(`ssh -D`), 기존 transmission-rpc.

**Spec:** `docs/superpowers/specs/2026-07-18-onejav-flaresolverr-design.md` (hardened, verify NEEDS_MORE_EVIDENCE 통과)

**실행 컨텍스트:** 랩탕 `girl` (Meridian-X 실행 주체). 본 계획은 어디서든 작성 가능하나 **Task 1(gate probe) 이후 단계는 girl에서 실행** — Playwright Chromium 설치·구동·heritage SSH가 girl 환경 전제.

## Global Constraints

- Python `>=3.12`, 패키지 매니저 `uv`. 신규 의존성은 `uv add`로 추가.
- Playwright **sync_api** 사용 (기존 동기 코드 스타일 유지, `asyncio` 도입 금지).
- `collect.py` 서명 무수정 — `discover(config)`/`resolve(item, config)` 시그니처 불변.
- SOCKS 터널: `ssh -N -D 127.0.0.1:<port> media@heritage`, `ExitOnForwardFailure=yes`, `IdentitiesOnly=yes`, `127.0.0.1` bind만(LAN 노출 금지).
- Chromium launch 옵션: `proxy={"server": "socks5://127.0.0.1:<port>"}`, `args=["--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1"]`, headless.
- `.torrent` 바이너리는 Playwright download 가로채기(`expect_download` + `save_as`)로 회수 — DOM/base64 경유 금지.
- 테스트는 도메인 로직만(`test_transmission.py` 스타일) — 네트워크/SSH/실제 Chromium 없이 mock 단위 테스트.
- 커밋: Conventional Commits, 말머리 영어, 본문 한국어.

---

## File Structure

| 파일 | 책임 | 신규/수정 |
| :--- | :--- | :--- |
| `pyproject.toml` | `playwright>=1.40` 의존성 추가 | 수정 |
| `scripts/probe_onejav_gate.py` | gate 통과 실증 프로브(Task 1, 전체 gate) | 신규 |
| `src/meridian_x/sources/onejav.py` | `_BrowserSession`/`_get_session`/`discover`/`resolve`/`_parse_rss`. `_ssh` 제거 | 전면 재작성 |
| `config/settings.json` + `.example` | `sources.onejav.socks_port` 추가 | 수정 |
| `tests/test_onejav_browser_session.py` | `_BrowserSession` 단위(mock) | 신규 |
| `tests/test_onejav_wiring.py` | `discover`/`resolve` wiring 단위(mock `_get_session`) | 신규 |

---

## Task 1: Playwright 의존성 + gate 통과 실증 (CRITICAL GATE)

**이 task는 전체 plan의 gate다.** Playwright 번들 Chromium가 SSH SOCKS経由 heritage egress에서 onejav `/feeds/` 에 200 + RSS를 반환하는지 실증. **모든 variant가 실패하면 Task 2~4를 진행하지 말고 spec 리스크 섹션에 기록 후 pivot(설계 재검토).**

**Files:**
- Modify: `pyproject.toml` (dependencies 배열)
- Create: `scripts/probe_onejav_gate.py`

**Interfaces:**
- Produces: gate 통과에 성공한 Chromium launch 설정(headless/channel/args) — 이 조합을 Task 2 `_BrowserSession.start()`의 launch 옵션으로 확정.

- [ ] **Step 1: Playwright 의존성 추가**

```bash
cd /home/crong/git/Meridian-X   # girl 환경에서는 해당 경로
uv add "playwright>=1.40"
```

예상 결과 — `pyproject.toml` `[project].dependencies` 에 아래 라인 추가:
```toml
    "playwright>=1.40",
```

- [ ] **Step 2: Chromium 브라우저 다운로드**

```bash
uv run playwright install chromium
# Linux 시스템 라이브러리 누락 에러 시에만:
uv run playwright install-deps chromium
```

예상 결과: Chromium 바이너리 다운로드 완료 (`~/.cache/ms-playwright/`).

- [ ] **Step 3: gate probe 스크립트 작성**

`scripts/probe_onejav_gate.py` 생성:

```python
#!/usr/bin/env python3
"""onejav Cloudflare gate 통과 실증 (TDD 1순위, 전체 plan의 gate).

Playwright Chromium가 SSH SOCKS(heritage residential egress)経由로
onejav /feeds/ 에 200 + <rss> 를 반환하는지 매트릭스 측정.
통과 조합을 stdout에 기록 → spec의 Chromium launch 옵션으로 확정.

실제 config(settings.json)의 remote 를 재사용. 네트워크·heritage SSH 필요.
"""
import json
import socket
import subprocess
import sys
import time

URL = "https://onejav.com/feeds/"
PORT = 10800


def _remote():
    from meridian_x.core import load_config
    cfg = load_config()
    r = cfg["remote"]
    return r["host"], r["user"], r["ssh_key"]


def open_tunnel(host, user, key):
    cmd = [
        "ssh", "-N", "-D", f"127.0.0.1:{PORT}",
        "-o", "ExitOnForwardFailure=yes", "-o", "ConnectTimeout=5",
        "-i", key, "-o", "IdentitiesOnly=yes", f"{user}@{host}",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for _ in range(20):
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", PORT)) == 0:
                return proc
        if proc.poll() is not None:
            sys.exit(f"tunnel died: {proc.stderr.read().decode()[:200]}")
        time.sleep(0.5)
    sys.exit(f"tunnel did not listen on {PORT}")


def try_variant(pw, name, **kw):
    launch_kw = {"headless": kw.get("headless", True),
                 "proxy": {"server": f"socks5://127.0.0.1:{PORT}"},
                 "args": ["--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1"]
                          + kw.get("args", [])}
    if kw.get("channel"):
        launch_kw["channel"] = kw["channel"]
    try:
        browser = pw.chromium.launch(**launch_kw)
        page = browser.new_context().new_page()
        resp = page.goto(URL, timeout=30000)
        body = resp.body()
        ua = page.evaluate("navigator.userAgent")
        webdriver = page.evaluate("navigator.webdriver")
        ok = resp.status == 200 and b"<rss" in body
        print(f"  [{name}] status={resp.status} len={len(body)} ok={ok} "
              f"ua={ua[:40]} webdriver={webdriver}")
        browser.close()
        return ok
    except Exception as e:
        print(f"  [{name}] ERR {repr(e)[:160]}")
        return False


def main():
    from playwright.sync_api import sync_playwright
    host, user, key = _remote()
    proc = open_tunnel(host, user, key)
    matrix = {}
    try:
        pw = sync_playwright().start()
        variants = [
            ("bundled-headless", {}),
            ("disable-blink", {"args": ["--disable-blink-features=AutomationControlled"]}),
            ("chrome-channel", {"channel": "chrome"}),
            ("bundled-headed", {"headless": False}),
        ]
        for name, kw in variants:
            matrix[name] = try_variant(pw, name, **kw)
            if matrix[name]:
                print(f">>> PASS variant: {name}")
                break
        pw.stop()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("MATRIX=" + json.dumps(matrix))
    if not any(matrix.values()):
        print("!!! GATE FAILED on all variants — PIVOT: Playwright 부족, 설계 재검토 필요")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: gate probe 실행 (전체 plan gate)**

```bash
cd /home/crong/git/Meridian-X
uv run python scripts/probe_onejav_gate.py
```

예상(통과 시): `>>> PASS variant: bundled-headless`(또는 다른 variant) + `MATRIX={"bundled-headless": true, ...}` + exit 0.

- [ ] **Step 5: gate 결과를 spec에 기록 + 결정**

- 통과 시: 통과한 variant·UA·webdriver 값을 spec "검증 2" 섹션에 기록. 그 variant의 launch 옵션이 Task 2 `_BrowserSession.start()`의 기준이 됨.
- **전 variant 실패 시**: 이 plan 중단. spec "리스크" 섹션에 "Playwright gate 미통과 실증" 추가 후 사용자와 pivot 논의 (Task 2~4 진행 금지).

- [ ] **Step 6: 커밋**

```bash
git add pyproject.toml uv.lock scripts/probe_onejav_gate.py
git commit -m "feat(onejav): Playwright 의존성 추가 + gate 통과 실증 프로브

real Chromium가 SSH SOCKS経유 onejav Cloudflare 통과 검증용 probe."
```

---

## Task 2: `_BrowserSession` + `_get_session` (단위 테스트)

SOCKS 터널 생명주기 + Chromium fetch 엔진. Task 1 통과 launch 설정을 `start()`에 반영.

**Files:**
- Modify: `src/meridian_x/sources/onejav.py` (imports + `_BrowserSession` + `_get_session` + `_BROWSER_SESSION` 전역 추가. 기존 `discover`/`resolve`/`_ssh`/`_parse_rss`는 그대로 유지 — Task 3에서 교체)
- Test: `tests/test_onejav_browser_session.py`

**Interfaces:**
- Consumes: `config["remote"]`(host/user/ssh_key), `config.get("socks_port", 10800)`, `config.get("request_timeout", 30)`
- Produces:
  - `_BrowserSession(config)` — 생성자(config 파싱만, 부작용 없음)
  - `session.start() -> None` — 터널 오픈 + Chromium launch
  - `session.fetch_bytes(url: str) -> bytes` — RSS/page raw body
  - `session.fetch_download(url: str) -> bytes` — `.torrent` 바이너리(다운로드 미발생 시 inline 응답 fallback)
  - `session.close() -> None` — idempotent 정리(terminate→wait→kill)
  - `_get_session(config) -> _BrowserSession` — lazy singleton + atexit 등록

- [ ] **Step 1: 실패 테스트 작성 — 포트 점유 + 터널 인자**

`tests/test_onejav_browser_session.py` 생성:

```python
"""_BrowserSession 단위 테스트. Playwright/네트워크/SSH 없이 순수 로직 검증.

test_transmission.py 스타일 — 도메인 로직만, RPC/브라우저/네트워크 포함 않음.
"""
import subprocess
from unittest.mock import MagicMock, patch

from meridian_x.sources import onejav


def _make_session(port=10800, timeout=30):
    """__init__ 없이 인스턴스 생성 (터널/브라우저 기동 회피)."""
    s = onejav._BrowserSession.__new__(onejav._BrowserSession)
    s._remote = {"host": "h", "user": "u", "ssh_key": "~/k"}
    s._port = port
    s._timeout_ms = timeout * 1000
    s._ssh_proc = None
    s._pw = None
    s._browser = None
    s._context = None
    s._page = None
    return s


class TestPortInUse:
    @patch("meridian_x.sources.onejav.socket")
    def test_free_port(self, msocket):
        msocket.socket.return_value.__enter__.return_value.connect_ex.return_value = 111
        assert _make_session()._port_in_use() is False

    @patch("meridian_x.sources.onejav.socket")
    def test_in_use(self, msocket):
        msocket.socket.return_value.__enter__.return_value.connect_ex.return_value = 0
        assert _make_session()._port_in_use() is True


class TestStartTunnel:
    @patch("meridian_x.sources.onejav.time")
    @patch("meridian_x.sources.onejav.subprocess")
    def test_cmd_has_hardening_flags(self, msub, mtime):
        s = _make_session(port=10800)
        msub.Popen.return_value.poll.return_value = None  # ssh alive
        # _port_in_use: 첫 검사(시작 전) False → Popen → 폴링에서 True
        with patch.object(onejav._BrowserSession, "_port_in_use",
                          side_effect=[False, True]):
            s._start_tunnel()
        cmd = msub.Popen.call_args[0][0]
        assert "-D" in cmd and "127.0.0.1:10800" in cmd
        assert "ExitOnForwardFailure=yes" in cmd
        assert "IdentitiesOnly=yes" in cmd
        assert "u@h" in cmd

    @patch("meridian_x.sources.onejav.time")
    @patch("meridian_x.sources.onejav.subprocess")
    def test_busy_port_triggers_stale_cleanup(self, msub, mtime):
        s = _make_session()
        msub.Popen.return_value.poll.return_value = None
        with patch.object(onejav._BrowserSession, "_port_in_use",
                          side_effect=[True, False, True]):
            with patch.object(onejav._BrowserSession, "_kill_stale_tunnel") as mk:
                s._start_tunnel()
        mk.assert_called_once()

    @patch("meridian_x.sources.onejav.time")
    @patch("meridian_x.sources.onejav.subprocess")
    def test_busy_after_cleanup_raises(self, msub, mtime):
        s = _make_session()
        with patch.object(onejav._BrowserSession, "_port_in_use",
                          side_effect=[True, True]):
            with patch.object(onejav._BrowserSession, "_kill_stale_tunnel"):
                import pytest
                with pytest.raises(RuntimeError, match="still in use"):
                    s._start_tunnel()
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/test_onejav_browser_session.py -v
```

예상: FAIL (`AttributeError: module has no attribute '_BrowserSession'` 또는 import 에러).

- [ ] **Step 3: imports + `_BrowserSession` + `_get_session` 구현**

`src/meridian_x/sources/onejav.py` 상단 imports를 아래로 교체하고, 기존 `_ssh` 함수 **직전**에 클래스·전역 추가. (기존 `discover`/`resolve`/`_parse_rss`는 이 단계에서 유지.)

새 imports (파일 최상단, docstring 직후):

```python
import atexit
import logging
import os
import re
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

_BROWSER_SESSION = None
```

`_ssh` 직전(또는 `discover` 직전)에 추가:

```python
class _BrowserSession:
    """SOCKS 터널(media@heritage) + Chromium 생명주기. lazy singleton(_get_session)経유."""

    def __init__(self, config: dict):
        self._remote = config["remote"]
        self._port = int(config.get("socks_port", 10800))
        self._timeout_ms = int(config.get("request_timeout", 30)) * 1000
        self._ssh_proc = None
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    # ---- SOCKS tunnel ----
    def _port_in_use(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", self._port)) == 0

    def _kill_stale_tunnel(self) -> None:
        # atexit 누수/강제 kill 잔존 정리 (fuser 로 포트 점유 프로세스 종료 시도)
        try:
            subprocess.run(
                ["fuser", "-k", f"{self._port}/tcp"],
                capture_output=True, timeout=5,
            )
        except Exception as e:
            logger.debug(f"stale tunnel cleanup skipped: {e}")

    def _start_tunnel(self) -> None:
        if self._port_in_use():
            logger.warning(f"port {self._port} in use — killing stale tunnel")
            self._kill_stale_tunnel()
            time.sleep(1)
            if self._port_in_use():
                raise RuntimeError(f"SOCKS port {self._port} still in use after cleanup")
        cmd = [
            "ssh", "-N",
            "-D", f"127.0.0.1:{self._port}",
            "-o", "ExitOnForwardFailure=yes",
            "-o", "ConnectTimeout=5",
            "-i", os.path.expanduser(self._remote["ssh_key"]),
            "-o", "IdentitiesOnly=yes",
            f'{self._remote["user"]}@{self._remote["host"]}',
        ]
        self._ssh_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for _ in range(20):
            if self._port_in_use():
                return
            if self._ssh_proc.poll() is not None:
                err = self._ssh_proc.stderr.read().decode(errors="replace")
                raise RuntimeError(f"SSH tunnel exited early: {err[:200]}")
            time.sleep(0.5)
        raise RuntimeError(f"SSH tunnel did not listen on {self._port} within 10s")

    # ---- browser ----
    def start(self) -> None:
        self._start_tunnel()
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=True,
            proxy={"server": f"socks5://127.0.0.1:{self._port}"},
            args=["--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1"],
        )
        self._context = self._browser.new_context()
        self._page = self._context.new_page()

    def fetch_bytes(self, url: str) -> bytes:
        resp = self._page.goto(url, timeout=self._timeout_ms, wait_until="domcontentloaded")
        return resp.body()

    def fetch_download(self, url: str) -> bytes:
        resp = None
        try:
            with self._page.expect_download(timeout=self._timeout_ms) as di:
                resp = self._page.goto(url, timeout=self._timeout_ms)
            download = di.value
            fd, path = tempfile.mkstemp(suffix=".torrent")
            os.close(fd)
            try:
                download.save_as(path)
                return Path(path).read_bytes()
            finally:
                Path(path).unlink(missing_ok=True)
        except PlaywrightTimeout:
            if resp is not None:
                logger.warning(f"download not fired for {url} — inline response fallback")
                return resp.body()
            raise

    def close(self) -> None:
        for obj in (self._page, self._context, self._browser, self._pw):
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass
        self._page = self._context = self._browser = self._pw = None
        if self._ssh_proc is not None and self._ssh_proc.poll() is None:
            self._ssh_proc.terminate()
            try:
                self._ssh_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._ssh_proc.kill()
        self._ssh_proc = None


def _get_session(config: dict) -> "_BrowserSession":
    global _BROWSER_SESSION
    if _BROWSER_SESSION is None:
        session = _BrowserSession(config)
        session.start()
        _BROWSER_SESSION = session
        atexit.register(session.close)
    return _BROWSER_SESSION
```

> **주의**: 파일에 이미 `import logging`/`import re`/`urljoin`/`logger`/`base64` 등이 있을 수 있다. 중복 import 제거하고 위 라인으로 통합. `base64` import는 Task 3에서 `_ssh` 제거 시 함께 정리.

- [ ] **Step 4: 터널 테스트 통과 확인**

```bash
uv run pytest tests/test_onejav_browser_session.py -v
```

예상: `TestPortInUse`(2), `TestStartTunnel`(3) PASS.

- [ ] **Step 5: 실패 테스트 추가 — close + fetch_bytes + fetch_download**

같은 파일(`tests/test_onejav_browser_session.py`)에 추가:

```python
class TestClose:
    def test_terminate_then_kill_on_timeout(self):
        s = _make_session()
        proc = MagicMock()
        proc.poll.return_value = None  # alive
        proc.wait.side_effect = subprocess.TimeoutExpired(cmd="ssh", timeout=5)
        s._ssh_proc = proc
        s._page = MagicMock()
        s._browser = MagicMock()
        s.close()
        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()

    def test_idempotent_when_all_none(self):
        s = _make_session()
        s.close()  # no raise
        s.close()


class TestFetchBytes:
    def test_returns_goto_response_body(self):
        s = _make_session()
        s._page = MagicMock()
        s._page.goto.return_value.body.return_value = b"<rss>x</rss>"
        assert s.fetch_bytes("https://onejav.com/feeds/") == b"<rss>x</rss>"
        s._page.goto.assert_called_once()


class TestFetchDownload:
    def _session_with_download(self, download_bytes=b"d8:announce4:test"):
        import shutil
        s = _make_session()
        page = MagicMock()
        src = Path(__file__)  # dummy; replaced per-test
        # expect_download 컨텍스트매니저: __enter__ -> di, di.value -> download
        di = MagicMock()
        download = MagicMock()

        def _save_as(dest):
            Path(dest).write_bytes(download_bytes)
            return None
        download.save_as.side_effect = _save_as
        di.value = download
        page.expect_download.return_value.__enter__.return_value = di
        s._page = page
        return s, page

    def test_success_returns_saved_bytes(self):
        s, _ = self._session_with_download(b"d8:announce4:test")
        assert s.fetch_download("https://x/dl.torrent") == b"d8:announce4:test"

    def test_fallback_on_timeout(self):
        from playwright.sync_api import TimeoutError as PWTimeout
        s = _make_session()
        page = MagicMock()
        resp = MagicMock()
        resp.body.return_value = b"dfallback-body"
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock()
        cm.__exit__.side_effect = PWTimeout("no download")
        page.goto.return_value = resp
        page.expect_download.return_value = cm
        s._page = page
        assert s.fetch_download("https://x/dl") == b"dfallback-body"
```

- [ ] **Step 6: 전체 _BrowserSession 테스트 통과 확인**

```bash
uv run pytest tests/test_onejav_browser_session.py -v
```

예상: 8개 테스트 전부 PASS.

- [ ] **Step 7: 커밋**

```bash
git add src/meridian_x/sources/onejav.py tests/test_onejav_browser_session.py
git commit -m "feat(onejav): _BrowserSession(SOCKS 터널 + Chromium fetch) 추가

lazy singleton + atexit, 포트 사전 정리, ExitOnForwardFailure,
terminate→wait→kill, .torrent expect_download + fallback."
```

---

## Task 3: `discover`/`resolve` 재작성 + config

`_ssh`/구 `discover`/`resolve`를 제거하고 `_get_session` 기반으로 교체. `socks_port` config 추가.

**Files:**
- Modify: `src/meridian_x/sources/onejav.py` (`_ssh` 제거, `discover`/`resolve` 재작성, 미사용 import 정리)
- Modify: `config/settings.json` + `config/settings.json.example` (`sources.onejav.socks_port` 추가)
- Test: `tests/test_onejav_wiring.py`

**Interfaces:**
- Consumes: Task 2의 `_get_session(config) -> session` (session.fetch_bytes / session.fetch_download)
- Produces: `discover(config) -> list[dict]`, `resolve(item, config) -> dict|None` (시그니처 불변, `collect.py` 무수정)

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_onejav_wiring.py` 생성:

```python
"""discover/resolve wiring 단위 테스트. _BrowserSession을 mock하여 순수 로직 검증."""
from unittest.mock import patch

from meridian_x.sources import onejav

RSS = (
    b'<?xml version="1.0"?><rss version="2.0"><channel>'
    b'<item><title>T1</title>'
    b'<link>http://onejav.com/torrent/abc123</link>'
    b'<description>d</description></item>'
    b'</channel></rss>'
)
PAGE = (
    b'<a href="/torrent/abc123/download/94694989/onejav.com_abc123.torrent">dl</a>'
)


class FakeSession:
    def __init__(self, rss=RSS, page=PAGE, torrent=b"d8:announce4:test"):
        self._rss, self._page, self._torrent = rss, page, torrent

    def fetch_bytes(self, url):
        return self._rss if "feeds" in url else self._page

    def fetch_download(self, url):
        return self._torrent


class TestDiscover:
    def test_parses_items_via_session(self):
        cfg = {"remote": {"host": "h"}, "rss_url": "https://onejav.com/feeds/"}
        with patch.object(onejav, "_get_session", return_value=FakeSession()):
            items = onejav.discover(cfg)
        assert len(items) == 1
        assert items[0]["id"] == "onejav:ABC123"
        assert items[0]["page_url"] == "http://onejav.com/torrent/abc123"

    def test_missing_remote_returns_empty(self):
        assert onejav.discover({"rss_url": "x"}) == []


class TestResolve:
    def _cfg(self):
        return {"remote": {"host": "h"}, "base_url": "https://onejav.com"}

    def test_extracts_torrent_bytes(self):
        item = {"page_url": "http://onejav.com/torrent/abc123"}
        with patch.object(onejav, "_get_session", return_value=FakeSession()):
            payload = onejav.resolve(item, self._cfg())
        assert payload["type"] == "metainfo"
        assert payload["data"].startswith(b"d8:announce")

    def test_no_download_link_returns_none(self):
        item = {"page_url": "http://onejav.com/torrent/abc123"}
        sess = FakeSession(page=b"<html>no link</html>")
        with patch.object(onejav, "_get_session", return_value=sess):
            assert onejav.resolve(item, self._cfg()) is None

    def test_non_bencode_returns_none(self):
        item = {"page_url": "http://onejav.com/torrent/abc123"}
        sess = FakeSession(torrent=b"NOTBENCODE!!!")
        with patch.object(onejav, "_get_session", return_value=sess):
            assert onejav.resolve(item, self._cfg()) is None

    def test_missing_remote_returns_none(self):
        assert onejav.resolve({"page_url": "x"}, {}) is None
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/test_onejav_wiring.py -v
```

예상: FAIL (구 `discover`/`resolve`가 SSH経유라 mock 세션을 안 씀, `non_bencode` 체크 없음 등).

- [ ] **Step 3: `discover`/`resolve` 재작성 + `_ssh` 제거**

`src/meridian_x/sources/onejav.py`에서 기존 `_ssh()` 함수와 구 `discover()`/`resolve()`를 삭제하고 아래로 교체 (`_parse_rss`는 유지):

```python
def discover(config: dict) -> list[dict]:
    """OneJAV RSS 수집. Playwright(real Chromium) + SSH SOCKS経유."""
    rss_url = config.get("rss_url", "https://onejav.com/feeds/")
    if not config.get("remote", {}).get("host"):
        logger.error("remote.host not configured")
        return []
    session = _get_session(config)
    try:
        rss_bytes = session.fetch_bytes(rss_url)
    except Exception as e:
        logger.error(f"OneJAV RSS fetch failed: {e}")
        return []
    return _parse_rss(rss_bytes.decode("utf-8", errors="replace"))


def resolve(item: dict, config: dict) -> dict | None:
    """페이지에서 .torrent 바이트 회수 → metainfo payload. Playwright + SOCKS経유."""
    page_url = item["page_url"]
    base_url = config.get("base_url", "https://onejav.com")
    if not config.get("remote", {}).get("host"):
        logger.error("remote.host not configured")
        return None
    session = _get_session(config)
    try:
        html = session.fetch_bytes(page_url).decode("utf-8", errors="replace")
    except Exception as e:
        logger.error(f"OneJAV page fetch failed for {page_url}: {e}")
        return None
    match = re.search(r'href="(/torrent/[^/]+/download/\d+/[^"]+\.torrent)"', html)
    if not match:
        logger.warning(f"No download link on {page_url}")
        return None
    download_url = urljoin(base_url, match.group(1))
    try:
        data = session.fetch_download(download_url)
    except Exception as e:
        logger.error(f"OneJAV torrent download failed for {download_url}: {e}")
        return None
    if not data or data[:1] != b"d":
        logger.warning(f"torrent payload not bencode for {download_url} (head={data[:8]!r})")
        return None
    return {"type": "metainfo", "data": data}
```

또한 더 이상 사용하지 않는 import(`base64` 등 `_ssh` 전용)를 제거. 최종 onejav.py imports는 Task 2 Step 3의 라인과 일치해야 함 (`base64` 제외).

- [ ] **Step 4: wiring 테스트 통과 확인**

```bash
uv run pytest tests/test_onejav_wiring.py -v
```

예상: 6개 테스트 전부 PASS.

- [ ] **Step 5: config에 socks_port 추가**

`config/settings.json.example` 의 `sources.onejav` 블록을 아래로 수정 (socks_port 추가):

```json
    "onejav": {
      "enabled": true,
      "base_url": "https://onejav.com",
      "rss_url": "https://onejav.com/feeds/",
      "socks_port": 10800
    },
```

`config/settings.json` (실제)에도 동일하게 `sources.onejav.socks_port: 10800` 추가. (`flaresolverr` 키는 예제에 없음; 실제 파일에 있다면 제거.)

- [ ] **Step 6: 전체 단위 테스트 + import 정상 확인**

```bash
uv run pytest tests/ -v
```

예상: `test_onejav_browser_session.py` + `test_onejav_wiring.py` + 기존 `test_transmission.py`/`test_simulation_classify.py` 전부 PASS. import 에러 없음.

- [ ] **Step 7: 커밋**

```bash
git add src/meridian_x/sources/onejav.py config/settings.json config/settings.json.example tests/test_onejav_wiring.py
git commit -m "feat(onejav): discover/resolve를 Playwright 세션経유로 재작성

_ssh 제거, bencode 무결성 체크, socks_port config 추가.
collect.py 무수정."
```

---

## Task 4: 통합 검증 (수동, end-to-end)

단위 테스트 통과 후 실제 파이프라인이 동작하는지 확인. 신규 코드 없음.

**Files:** (변경 없음)

- [ ] **Step 1: gate probe 회귀 (재확인)**

```bash
uv run python scripts/probe_onejav_gate.py
```

예상: exit 0, `MATRIX`에 `true` 최소 1개.

- [ ] **Step 2: dry-run — items 발견**

```bash
uv run meridian transmission --source onejav --dry-run
```

예상: `Found N items`, dry-run 항목 출력. (`Found 0` 시 게이트/파싱 재확인.)

- [ ] **Step 3: `.torrent` bencode 무결성 fixture**

resolve가 반환한 `.torrent` 1개를 실제로 받아 bencode 파싱 가능한지 확인. 1회성 스크립트로 회수:

```bash
uv run python -c "
from meridian_x.sources import onejav
from meridian_x.core import load_config
cfg = load_config()
eff = {**cfg.get('collection',{}), **cfg['sources']['onejav'], 'remote': cfg['remote']}
items = onejav.discover(eff)
payload = onejav.resolve(items[0], eff)
d = payload['data']
print('len', len(d), 'head', d[:16])
# bencode 최소 검증: d 로 시작 + announce 또는 info 키
assert d[:1]==b'd' and (b'8:announce' in d or b'4:info' in d), 'not valid bencode'
print('BENCODE OK')
"
```

예상: `BENCODE OK`. (bencode 파싱 라이브러리가 있으면 `bencodepy.decode(d)` 로 완전 검증 권장.)

- [ ] **Step 4: Transmission 전송 (max-downloads 1)**

```bash
uv run meridian transmission --source onejav --max-downloads 1
```

예상: `[Sent] onejav:...` 1건, Transmission UI에 토렌트 추가 확인.

- [ ] **Step 5: 회귀 — 타 source 무영향**

```bash
uv run meridian transmission --source xxxclub --dry-run
```

예상: xxxclub 정상 동작 (onejav 변경이 타 source에 영향 없음).

- [ ] **Step 6: 종료 — 잔존 터널/프로세스 정리 확인**

```bash
ss -tln | grep 10800 || echo "port 10800 clean"
pgrep -af "ssh.*-D 127.0.0.1:10800" || echo "no stale tunnel"
```

예상: `clean` / `no stale tunnel` (atexit 정리 동작 확인).

- [ ] **Step 7: (정리) 사용자에게 산출물 + 결과 보고**

- spec(`docs/superpowers/specs/2026-07-18-onejav-flaresolverr-design.md`) 검증 섹션에 gate 통과 variant·통합 결과 기록.
- homelab spec(`docs/superpowers/specs/2026-07-18-flaresolverr-heritage-design.md`)은 SUPERSEDED 상태 유지 (삭제 여부 사용자 판단).
- 커밋되지 않은 변경 없음 확인 후 사용자에게 완료 보고.

---

## Self-Review

**1. Spec coverage:**
- 핵심 설계(Playwright + SOCKS, real Chromium만 통과): Task 1(gate) + Task 2(`_BrowserSession`). ✓
- DNS leak 방지(`--host-resolver-rules`): Task 2 launch args + Task 1 probe. ✓ (런타임 leak 단위 테스트는 랩탕 환경에서 별도 수동 측정 권장 — plan에 명시적 단계는 없으나 probe가 egress를 확인)
- atexit/lifecycle(포트 정리, ExitOnForwardFailure, terminate/wait/kill): Task 2 + Task 4 Step 6. ✓
- 바이너리 무결성(fetch_bytes/expect_download + fallback): Task 2 + Task 4 Step 3 fixture. ✓
- config(socks_port, flaresolverr 제거): Task 3 Step 5. ✓
- 검증(단위/gate/통합/회귀): Task 2·3 단위, Task 1 gate, Task 4 통합+회귀. ✓
- collect.py 무수정: discover/resolve 시그니처 보존 (Task 3). ✓

**2. Placeholder scan:** "TODO/TBD/적절히" 없음. 모든 코드 단계에 실제 코드. ✓

**3. Type consistency:** `fetch_bytes(url)->bytes`, `fetch_download(url)->bytes`, `_get_session(config)->_BrowserSession`, `discover(config)->list[dict]`, `resolve(item,config)->dict|None` — Task 2 정의 → Task 3 사용 일치. `socks_port`/`request_timeout`/`remote` config 키 양쪽 일치. ✓

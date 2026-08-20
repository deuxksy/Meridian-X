# Meridian-X 전면 리팩토링 및 최적화 구현 계획서 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 코드 중복 완전 제거(DRY), `remote.py` 원격 통신 모듈 신설, `requests.Session` Keep-Alive 풀링, 미사용 레거시 코드 제거를 통해 Meridian-X를 가장 우아하고 견고한 아키텍처로 전면 리팩토링한다.

**Architecture:** 원격 SSH/Curl 호출을 `src/meridian_x/remote.py`로 일원화하고, 4대 소스(`onejav`, `sukebei`, `torrentgalaxy`), `jav_lookup`, `tidy`, `classify`, `report`가 이를 재사용하도록 마이그레이션한다. API 클라이언트(`fanza`, `jellyfin`, `west_metadata`)에 세션 풀링을 적용하고, `core.py`의 미사용 레거시 함수를 정리한다.

**Tech Stack:** Python 3.12, Requests (Session), Transmission-RPC, SQLite3 (MeridianDB), Pytest, Pytest-Mock.

## Global Constraints

- Python 커맨드는 항상 `uv run`을 통해 가상환경 의존성 내에서 실행한다.
- 용어 규칙을 철저히 준수한다: '성인' 대신 '신사' / '프라이빗 미디어' / '품격 있는 큐레이션' 표현 사용.
- 모든 변경은 TDD로 검증하며, 기존 122개 테스트 통과 상태를 100% 유지한다.
- 불필요한 의존성 추가 없이 순수 표준 라이브러리 및 기존 의존성만 사용한다.

---

### Task 1: 원격 통신 모듈 (`src/meridian_x/remote.py`) 신설 및 단위 테스트

**Files:**
- Create: `src/meridian_x/remote.py`
- Test: `tests/test_remote.py`

**Interfaces:**
- Produces:
  - `fetch_remote_curl(url: str, ssh_alias: str = "lt", timeout: int = 15, headers: dict = None, follow_redirects: bool = True, use_ipv4: bool = True) -> str`
  - `run_remote_ssh(host: str, command: str, user: str = None, connect_timeout: int = 5, timeout: int = 15, dry_run: bool = False) -> subprocess.CompletedProcess`

- [ ] **Step 1: Write failing tests for `remote.py`**

```python
# tests/test_remote.py
import subprocess
from unittest.mock import MagicMock, patch
import pytest
from meridian_x.remote import fetch_remote_curl, run_remote_ssh


def test_fetch_remote_curl_success():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="<html>content</html>")
        res = fetch_remote_curl("https://example.com", ssh_alias="lt", timeout=10)
        assert res == "<html>content</html>"
        
        args = mock_run.call_args[0][0]
        assert "ssh" in args
        assert "lt" in args
        assert "-4" in args[4]
        assert "https://example.com" in args[4]


def test_fetch_remote_curl_error_returns_empty():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="Connection failed")
        res = fetch_remote_curl("https://example.com", ssh_alias="lt")
        assert res == ""


def test_fetch_remote_curl_custom_headers():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok")
        fetch_remote_curl("https://example.com", headers={"X-Custom": "Val"})
        args = mock_run.call_args[0][0]
        assert "-H 'X-Custom: Val'" in args[4] or '-H "X-Custom: Val"' in args[4]


def test_run_remote_ssh_dry_run():
    with patch("subprocess.run") as mock_run:
        res = run_remote_ssh("nas.host", "ls -la", user="media", dry_run=True)
        assert res.returncode == 0
        mock_run.assert_not_called()


def test_run_remote_ssh_execution():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="output\n", stderr="")
        res = run_remote_ssh("nas.host", "ls -la", user="media")
        assert res.returncode == 0
        args = mock_run.call_args[0][0]
        assert args[0] == "ssh"
        assert "media@nas.host" in args
        assert "ls -la" in args
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_remote.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'meridian_x.remote'`

- [ ] **Step 3: Implement `src/meridian_x/remote.py`**

```python
# src/meridian_x/remote.py
"""
Meridian-X Remote Execution & Proxy Fetch Module
원격 SSH 및 프록시 Curl 실행 전용 모듈
"""
import logging
import subprocess
from typing import Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_remote_curl(
    url: str,
    ssh_alias: str = "lt",
    timeout: int = 15,
    headers: Optional[Dict[str, str]] = None,
    follow_redirects: bool = True,
    use_ipv4: bool = True,
) -> str:
    """원격 SSH 프록시(Oracle Cloud KR 등)를 경유하여 curl로 웹 페이지를 안전하게 수집합니다."""
    if not url:
        return ""

    curl_flags = []
    if use_ipv4:
        curl_flags.append("-4")
    curl_flags.append("-sL" if follow_redirects else "-s")
    curl_flags.append(f"--max-time {timeout}")

    # Header configuration
    req_headers = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        req_headers.update(headers)

    for k, v in req_headers.items():
        curl_flags.append(f'-H "{k}: {v}"')

    curl_flags_str = " ".join(curl_flags)
    cmd = [
        "ssh",
        "-o",
        "ConnectTimeout=5",
        ssh_alias,
        f'curl {curl_flags_str} "{url}"',
    ]

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        if res.returncode != 0:
            logger.warning(
                f"fetch_remote_curl non-zero ({res.returncode}) for {url}: {res.stderr.strip()}"
            )
            return ""
        return res.stdout
    except subprocess.TimeoutExpired:
        logger.warning(f"fetch_remote_curl timed out for {url}")
        return ""
    except Exception as e:
        logger.error(f"fetch_remote_curl unexpected error for {url}: {e}")
        return ""


def run_remote_ssh(
    host: str,
    command: str,
    user: Optional[str] = None,
    connect_timeout: int = 5,
    timeout: int = 15,
    dry_run: bool = False,
) -> subprocess.CompletedProcess:
    """NAS 또는 원격 서버에 SSH 명령을 안전하게 실행합니다."""
    target = f"{user}@{host}" if user else host
    if dry_run:
        logger.info(f"[Dry-run SSH] Would run on {target}: {command}")
        return subprocess.CompletedProcess(
            args=["ssh", target, command],
            returncode=0,
            stdout="[Dry-run] OK\n",
            stderr="",
        )

    cmd = [
        "ssh",
        "-o",
        f"ConnectTimeout={connect_timeout}",
        target,
        command,
    ]

    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as e:
        logger.error(f"run_remote_ssh error on {target}: {e}")
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=1,
            stdout="",
            stderr=str(e),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_remote.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/meridian_x/remote.py tests/test_remote.py
git commit -m "feat(remote): add unified remote SSH and proxy curl execution module"
```

---

### Task 2: 4대 소스 모듈 및 JavLookup 마이그레이션

**Files:**
- Modify: `src/meridian_x/sources/onejav.py`
- Modify: `src/meridian_x/sources/sukebei.py`
- Modify: `src/meridian_x/sources/torrentgalaxy.py`
- Modify: `src/meridian_x/jav_lookup.py`
- Test: `tests/test_onejav_security.py`, `tests/test_sukebei.py`, `tests/test_torrentgalaxy.py`, `tests/test_jav_lookup.py`

**Interfaces:**
- Consumes: `meridian_x.remote.fetch_remote_curl`

- [ ] **Step 1: Update `onejav.py`, `sukebei.py`, `torrentgalaxy.py`, `jav_lookup.py` to use `fetch_remote_curl`**
- [ ] **Step 2: Run all source tests to verify regression safety**

Run: `uv run pytest tests/test_onejav_security.py tests/test_sukebei.py tests/test_torrentgalaxy.py tests/test_jav_lookup.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/meridian_x/sources/onejav.py src/meridian_x/sources/sukebei.py src/meridian_x/sources/torrentgalaxy.py src/meridian_x/jav_lookup.py tests/
git commit -m "refactor(sources): migrate proxy curl fetch to remote.fetch_remote_curl"
```

---

### Task 3: NAS 원격 명령(`tidy.py`, `classify.py`, `report.py`) 마이그레이션

**Files:**
- Modify: `src/meridian_x/tidy.py`
- Modify: `src/meridian_x/classify.py`
- Modify: `src/meridian_x/report.py`
- Test: `tests/test_tidy.py`, `tests/test_classify.py`

**Interfaces:**
- Consumes: `meridian_x.remote.run_remote_ssh`

- [ ] **Step 1: Replace raw `subprocess.run(["ssh", ...])` in `tidy.py`, `classify.py`, `report.py` with `run_remote_ssh`**
- [ ] **Step 2: Run tests to verify**

Run: `uv run pytest tests/test_tidy.py tests/test_classify.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/meridian_x/tidy.py src/meridian_x/classify.py src/meridian_x/report.py tests/
git commit -m "refactor(ssh): unify remote NAS operations with remote.run_remote_ssh"
```

---

### Task 4: HTTP 세션 풀링 (`requests.Session`) 적용

**Files:**
- Modify: `src/meridian_x/fanza.py`
- Modify: `src/meridian_x/jellyfin.py`
- Modify: `src/meridian_x/west_metadata.py`
- Test: `tests/test_jellyfin.py`, `tests/test_west_metadata.py`, `tests/test_jav_metadata.py`

**Interfaces:**
- Keeps existing public client signatures, uses internal `self.session`

- [ ] **Step 1: Refactor `fanza.py`, `jellyfin.py`, `west_metadata.py` to use `requests.Session()` with connection pooling**
- [ ] **Step 2: Run tests to verify**

Run: `uv run pytest tests/test_jellyfin.py tests/test_west_metadata.py tests/test_jav_metadata.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/meridian_x/fanza.py src/meridian_x/jellyfin.py src/meridian_x/west_metadata.py
git commit -m "perf(http): introduce requests.Session connection pooling in API clients"
```

---

### Task 5: `core.py` 및 `cli.py` 레거시 정리 & 정규화

**Files:**
- Modify: `src/meridian_x/core.py`
- Modify: `src/meridian_x/cli.py`
- Test: `tests/test_core.py`

**Interfaces:**
- Remove deprecated `load_downloaded_history` and `save_downloaded_history` from `core.py`
- Clean up duplicate `_get_magnet` in `cli.py`

- [ ] **Step 1: Remove legacy history functions from `core.py` and remove associated legacy tests in `test_core.py`**
- [ ] **Step 2: Clean up and streamline `cli.py` search & pipeline execution**
- [ ] **Step 3: Run `tests/test_core.py`**

Run: `uv run pytest tests/test_core.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/meridian_x/core.py src/meridian_x/cli.py tests/test_core.py
git commit -m "refactor(core): remove legacy history wrappers and streamline cli workflows"
```

---

### Task 6: 전체 회귀 테스트 및 문서 정합성 점검

**Files:**
- Modify: `.ai/RULES.md`
- Modify: `README.md`

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: ALL 100% PASS

- [ ] **Step 2: Check git status and documentation integrity**

Run: `git status -s`

- [ ] **Step 3: Commit**

```bash
git add .ai/RULES.md README.md
git commit -m "docs: update architecture in RULES.md and README.md for v0.8.0 refactored core"
```

# Meridian-X 전면 리팩토링 및 최적화 설계 명세서 (Design Spec)

- **Date**: 2026-08-20
- **Status**: Approved
- **Target Version**: v0.8.0-dev

---

## 1. 개요 및 목표 (Overview & Goals)

Meridian-X 프로젝트가 4대 소스(OneJAV, Sukebei, XXXClub, TorrentGalaxy) 통합, 메타데이터 연동, 고화질/릴리스 우선순위 선별 엔진 등으로 확장됨에 따라 코드 중복을 제거하고 통신 성능과 유지보수성을 극대화하기 위한 종합 리팩토링을 수행한다.

### 핵심 원칙
1. **DRY (Don't Repeat Yourself)**: 4대 소스 및 메타데이터/SSH 유틸리티 전반에 걸친 원격 curl/SSH 코드 통합
2. **KISS & YAGNI**: 파일(txt) 기반 레거시 래퍼 및 미사용 코드 완전 제거
3. **성능 최적화**: `requests.Session` Keep-Alive 풀링을 통한 TCP/TLS 핸드셰이크 오버헤드 최소화
4. **엄격한 안정성**: 전체 회귀 테스트 100% 통과 보장

---

## 2. 상세 아키텍처 및 모듈 설계

### 2.1 원격 통신 전용 모듈 (`src/meridian_x/remote.py`) 신설

```python
"""
Meridian-X Remote Execution & Proxy Fetch Module
"""
import logging
import subprocess
from typing import Optional, Dict

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def fetch_remote_curl(
    url: str,
    ssh_alias: str = "lt",
    timeout: int = 15,
    headers: Optional[Dict[str, str]] = None,
    follow_redirects: bool = True,
    use_ipv4: bool = True,
) -> str:
    """원격 SSH 프록시(Oracle Cloud KR 등)를 경유하여 curl로 웹 페이지/데이터 수집."""
    ...

def run_remote_ssh(
    host: str,
    command: str,
    user: Optional[str] = None,
    connect_timeout: int = 5,
    timeout: int = 15,
    dry_run: bool = False,
) -> subprocess.CompletedProcess:
    """NAS/원격 호스트에 SSH 명령을 안전하게 실행."""
    ...
```

#### 적용 대상
- `src/meridian_x/sources/onejav.py`: 자체 `fetch_url_remote` 제거 ➡️ `remote.fetch_remote_curl` 사용
- `src/meridian_x/sources/sukebei.py`: 자체 `fetch_url_remote` 제거 ➡️ `remote.fetch_remote_curl` 사용
- `src/meridian_x/sources/torrentgalaxy.py`: 자체 `fetch_url_remote` 제거 ➡️ `remote.fetch_remote_curl` 사용
- `src/meridian_x/jav_lookup.py`: `_fetch_page_via_ssh` 제거 ➡️ `remote.fetch_remote_curl` 사용
- `src/meridian_x/report.py`: SSH subprocess 호출 ➡️ `remote.run_remote_ssh` 사용
- `src/meridian_x/tidy.py`: SSH subprocess 호출 ➡️ `remote.run_remote_ssh` 사용
- `src/meridian_x/classify.py`: SSH subprocess 호출 ➡️ `remote.run_remote_ssh` 사용

---

### 2.2 HTTP 세션 풀링 (`requests.Session`) 적용

단발성 `requests.get()` / `requests.post()` 호출을 클래스 인스턴스 소유 `requests.Session()`으로 전환하여 TCP 커넥션 재사용 및 Keep-Alive 적용.

#### 적용 대상
1. **`src/meridian_x/fanza.py` (`FanzaClient`)**:
   - `self.session = requests.Session()` 초기화
   - API 요청 시 `self.session.get()` 호출
2. **`src/meridian_x/jellyfin.py` (`JellyfinClient`)**:
   - `self.session = requests.Session()`에 기본 인증 헤더(`X-Emby-Token` 등) 사전 등록
   - `self.session.get/post/delete()` 호출
3. **`src/meridian_x/west_metadata.py` (`StashDBClient`)**:
   - `self.session = requests.Session()`에 `ApiKey` 헤더 등록 후 GraphQL 쿼리 전송

---

### 2.3 `core.py` 및 `cli.py` 레거시 정리

1. **`src/meridian_x/core.py`**:
   - `load_downloaded_history()` 및 `save_downloaded_history()` 삭제 (`MeridianDB`로 대체)
   - 화질 검사(`is_fhd_or_higher`), 릴리스 스코어링(`score_release`), 중복 제거(`deduplicate_releases`), 씬 키 추출(`extract_scene_key`)의 타입 명시 강화
2. **`src/meridian_x/cli.py`**:
   - `_get_magnet` 중복 정의 통합
   - `run_search` 내부의 대화형 / 자동 다운로드 루프를 가독성 높게 분리

---

## 3. 테스트 및 검증 전략

1. **신규 단위 테스트**:
   - `tests/test_remote.py`: `fetch_remote_curl` (정상 파싱, 타임아웃, 헤더, 커스텀 옵션) 및 `run_remote_ssh` (dry-run, 실패 처리) 테스트
2. **기존 테스트 업데이트**:
   - `tests/test_core.py`: 삭제된 레거시 함수 테스트 제거
   - `tests/test_sukebei.py`, `tests/test_torrentgalaxy.py`, `tests/test_onejav_security.py`: `remote.py` 모킹 및 위임 검증
3. **전체 회귀 검증**:
   - `uv run pytest tests/ -v` (100% 패스 유지)

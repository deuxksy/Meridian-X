# onejav Favorite 수집 + 사용하지 않는 기능 정리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** onejav 즐겨찾기 페이지(token URL)의 `.torrent` 링크를 정기 수집에 병합하고, dead flag·만료 진단 스크립트·SSH locale 버그를 정리한다.

**Architecture:** `onejav.discover_favorite()`를 기존 `discover()`(RSS)와 분리된 경로로 추가 — FlareSolverr 1회 fetch로 HTML에서 직접 링크를 추출하고 item에 cf_clearance cookie를 실어 `resolve()`가 페이지 재fetch 없이 다운로드하게 한다. `collect.py`는 `hasattr`로 병합한다. SSH locale 경고는 `run_remote_ssh()`의 ssh 옵션에 `SetEnv=LC_ALL=C`를 추가해 원천 차단한다(2026-11-14 실측으로 효과 확인됨).

**Tech Stack:** Python 3.12+, pytest + pytest-mock(mocker)/unittest.mock, requests, uv

**Spec:** `docs/superpowers/specs/2026-11-14-onejav-favorite-and-cleanup-design.md`

## Global Constraints

- 신규 의존성 추가 금지
- secret 평문 git 커밋 금지 — favorite token URL은 `config/settings.json`(gitignored)과 `settings.json.sops`에만 존재. **plan/커밋 메시지/로그에 token 값 기입 금지**
- 로그/주석은 기존 모듈의 한국어 스타일 유지
- 커밋: Conventional Commits, 말머리 영어 + 본문 한국어
- 원격/외부 시스템 변경 없음(이 plan의 모든 단계는 로컬 + 테스트. 단 Task 6의 sops 갱신과 Task 7 dry-run은 실제 config/네트워크 사용하나 쓰기 없음)

## Review Focus

1. **동일 run 내 RSS·favorite 품번 중복** — 같은 id(`onejav:SUJI325`)가 두 경로에 있으면 이중 add 방지 → Task 2 병합 시 id 기준 dedup 테스트
2. **favorite_url 미설정/빈 값** — 기존 수집 경로 0영향, `discover_favorite()` 조용히 빈 리스트 → Task 1 테스트
3. **악의적/이탈 호스트** — favorite_url과 추출된 download_url은 `_validate_url`(onejav.com allowlist) 통과해야 → Task 1 테스트
4. **FlareSolverr 실패** — 경고 로그 + 빈 리스트 반환, collect의 per-source boundary가 전체 수집을 지켜야 → Task 1 테스트
5. **cf_clearance 만료(장시간 지연 후 resolve)** — `download_via_proxy`가 None → item skip 경고, crash 없음 → Task 1 resolve bypass 테스트에서 None 반환 케이스

---

### Task 1: onejav `discover_favorite()` + `resolve()` 직접 다운로드 bypass

**Files:**
- Modify: `src/meridian_x/sources/onejav.py`
- Test: `tests/test_onejav_favorite.py` (신규)

**Interfaces:**
- Consumes: 기존 `DOWNLOAD_HREF_RE`, `_validate_url`, `_safe_timeout`, `fetch_via_flaresolverr`, `download_via_proxy` (remote.py)
- Produces:
  - `_parse_favorite(html: str, base_url: str) -> list[dict]` — 순수 파서. item: `{"id": "onejav:<CODE>", "title": "<CODE>", "download_url": "<abs url>"}`. CODE는 href 경로 `/torrent/<code>/download/...`에서 추출, 대문자화 (기존 RSS id 규칙과 동일)
  - `discover_favorite(config: dict) -> list[dict]` — `config["favorite_url"]` 없으면 `[]`. FlareSolverr fetch 후 파서 결과 각 item에 `cookies`/`user_agent`(fetch 결과 공유 참조) 추가
  - `resolve(item, config)` — `item.get("download_url")` 있으면 페이지 fetch 생략하고 `download_via_proxy(item["download_url"], config, cookies=item["cookies"], user_agent=item["user_agent"])`로 즉시 metainfo 반환

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_onejav_favorite.py`에 5개 케이스 (Review Focus 2~5 + 파싱 정상 케이스):

```python
FAVORITE_HTML = '''<html><body>
<a href="/torrent/suji325/download/17043913/onejav.com_suji325.torrent">dl</a>
<a href="/torrent/mvsd710_2/download/00891138/onejav.com_mvsd710_2.torrent">dl</a>
</body></html>'''

def test_parse_favorite_extracts_items():
    items = _parse_favorite(FAVORITE_HTML, "https://onejav.com")
    assert items[0]["id"] == "onejav:SUJI325"
    assert items[0]["download_url"] == "https://onejav.com/torrent/suji325/download/17043913/onejav.com_suji325.torrent"
    assert len(items) == 2

def test_discover_favorite_no_url_returns_empty():
    assert discover_favorite({}) == []

def test_discover_favorite_success(mocker):
    mocker.patch("meridian_x.sources.onejav.fetch_via_flaresolverr",
                 return_value={"html": FAVORITE_HTML, "user_agent": "UA", "cookies": {"cf_clearance": "tok"}})
    items = discover_favorite({"favorite_url": "https://onejav.com/favorite/TOKEN"})
    assert items[0]["id"] == "onejav:SUJI325"
    assert items[0]["cookies"] == {"cf_clearance": "tok"}
    assert items[0]["user_agent"] == "UA"

def test_discover_favorite_flaresolverr_fail(mocker):
    mocker.patch("meridian_x.sources.onejav.fetch_via_flaresolverr", return_value=None)
    assert discover_favorite({"favorite_url": "https://onejav.com/favorite/TOKEN"}) == []

def test_resolve_download_url_bypass(mocker):
    mocker.patch("meridian_x.sources.onejav.download_via_proxy", return_value=b"BIN")
    item = {"id": "onejav:SUJI325", "download_url": "https://onejav.com/torrent/suji325/download/1/x.torrent",
            "cookies": {"cf_clearance": "tok"}, "user_agent": "UA"}
    payload = resolve(item, {"proxy": "http://p:8080"})
    assert payload == {"type": "metainfo", "data": b"BIN"}
    # 페이지 fetch(fetch_via_flaresolverr)는 호출되지 않음

def test_resolve_download_url_download_fail(mocker):
    # cf_clearance 만료 등으로 download가 None → resolve도 None (crash 없음)
    mocker.patch("meridian_x.sources.onejav.download_via_proxy", return_value=None)
    item = {"id": "onejav:SUJI325", "download_url": "https://onejav.com/torrent/suji325/download/1/x.torrent",
            "cookies": {"cf_clearance": "tok"}, "user_agent": "UA"}
    assert resolve(item, {"proxy": "http://p:8080"}) is None
```

호스트 검증 케이스 추가: `favorite_url`이 `https://evil.com/fav`면 `discover_favorite`이 `[]` (`_validate_url` 실패 로그).

- [ ] **Step 2: 테스트 실행 실패 확인** — `uv run pytest tests/test_onejav_favorite.py -v` → ImportError(`_parse_favorite` 없음)

- [ ] **Step 3: 구현** — `onejav.py`에 `_parse_favorite`(`DOWNLOAD_HREF_RE.finditer`, `urljoin(base_url, href)`, code는 group에서 `/torrent/([^/]+)/` 추출), `discover_favorite`(early return → `_validate_url(favorite_url)` → fetch → parse → cookies/user_agent 부착), `resolve()` 선두에 download_url bypass (download_url도 `_validate_url` 검증 후 `download_via_proxy`, timeout은 `_safe_timeout(config) + 10`). download 실패(None) 시 `None` 반환 — 기존 실패 패턴과 동일

- [ ] **Step 4: 테스트 통과 확인** — `uv run pytest tests/test_onejav_favorite.py -v` → 전부 PASS

- [ ] **Step 5: Commit** — `git add src/meridian_x/sources/onejav.py tests/test_onejav_favorite.py` → `feat(onejav): 즐겨찾기 페이지 .torrent 링크 수집 경로 추가`

### Task 2: collect.py favorite 병합 (id dedup 포함)

**Files:**
- Modify: `src/meridian_x/collect.py:88-95` (`items = src_module.discover(...)` 직후)
- Test: `tests/test_collect.py` (기존 파일에 추가)

**Interfaces:**
- Consumes: Task 1의 `discover_favorite(config) -> list[dict]`, item `id` 규칙 `onejav:<CODE>`
- Produces: `run_transmission` 병합 동작 (후속 태스크가 의존하지 않음 — 최종 산출물)

- [ ] **Step 1: 실패 테스트 작성** — fake source module로 2케이스:

```python
def test_collect_merges_favorite_items(mocker):
    # discover → [{"id": "onejav:A"}], discover_favorite → [{"id": "onejav:B"}]
    # run_transmission 실행 시 두 item 모두 처리 (로그/전송 호출 2회)
def test_collect_favorite_duplicate_id_skipped(mocker):
    # discover → [{"id": "onejav:A"}], discover_favorite → [{"id": "onejav:A"}]
    # 동일 run 내 이중 처리 방지 → 실제 처리 1회
```

기존 `test_collect.py`의 mocker 패턴(`requests.get`, TransmissionClient mock)을 참조해 `TransmissionClient`, `MeridianDB`, 두 discover 함수를 mock. `favorite_url` 미설정이면 `discover_favorite`을 호출하지 않는 것도 단언.

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_collect.py -v -k favorite` → FAIL (병합 로직 없음)

- [ ] **Step 3: 구현** — discover 직후:

```python
if hasattr(src_module, "discover_favorite") and src_config.get("favorite_url"):
    fav_items = src_module.discover_favorite(effective_config)
    existing_ids = {i["id"] for i in items}
    fav_new = [i for i in fav_items if i["id"] not in existing_ids]
    if fav_new:
        logger.info(f"[favorite] {len(fav_new)} items")
        items = items + fav_new
```

- [ ] **Step 4: 통과 확인** — `uv run pytest tests/test_collect.py -v` → 전부 PASS

- [ ] **Step 5: Commit** — `git add src/meridian_x/collect.py tests/test_collect.py` → `feat(collect): 소스별 favorite 수집 결과 병합 및 중복 id 제거`

### Task 3: cli.py `--favorite` dead flag 제거

**Files:**
- Modify: `src/meridian_x/cli.py:266-271` (argparse `--favorite` 블록)
- Test: `tests/test_cli.py` (신규)

**Interfaces:**
- Consumes: 없음
- Produces: `--favorite` 인자 제거 (더 이상 어디서도 참조 없음 — 이미 소비 코드 0)

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_cli.py`에 `--favorite` 전달 시 argparse가 종료 code 2로 거부하는지. **현재 단계(플래그 존재)에 실제 수집이 돌지 않도록 `meridian_x.collect.run_transmission`을 mock** (cli.py가 dispatch 시점에 `from .collect import run_transmission`으로 import하므로 원본 모듈에 패치):

```python
def test_favorite_flag_removed(capsys, mocker):
    mocker.patch("meridian_x.collect.run_transmission")
    with patch("sys.argv", ["meridian", "transmission", "--source", "onejav", "--favorite", "https://onejav.com/x"]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 2
        assert "unrecognized arguments" in capsys.readouterr().err
```

import 시점 로그 디렉토리 생성 부작용은 기존 cli.py 동작과 동일하므로 방치.

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_cli.py -v` → FAIL. 현재는 `--favorite`이 유효 인자라 argparse가 통과되고 mock된 `run_transmission`만 호출 → `pytest.raises(SystemExit)`가 발동하지 않아 `DID NOT RAISE`

- [ ] **Step 3: 구현** — cli.py에서 `--favorite` add_argument 블록 삭제. epilog 예시에 `--favorite` 없는지도 확인(현재 없음)

- [ ] **Step 4: 통과 확인** — `uv run pytest tests/test_cli.py -v` → PASS

- [ ] **Step 5: Commit** — `git add src/meridian_x/cli.py tests/test_cli.py` → `refactor(cli): 미사용 --favorite 플래그 제거`

### Task 4: probe 스크립트 삭제

**Files:**
- Delete: `scripts/probe_onejav_gate.py`, `scripts/probe_onejav_ech.py`

**Interfaces:** 없음 (독립 파일, import 참조 없음 — 삭제 전 `grep -rn "probe_onejav" src/ tests/`로 0건 확인)

- [ ] **Step 1: 참조 확인** — `grep -rn "probe_onejav" src/ tests/ docs/ README.md` → 0건 (docs 언급 시 해당 줄 정리)
- [ ] **Step 2: 삭제** — `git rm scripts/probe_onejav_gate.py scripts/probe_onejav_ech.py`
- [ ] **Step 3: 회귀** — `uv run pytest tests/ -q` → 기존 전량 PASS
- [ ] **Step 4: Commit** — `chore: 만료된 onejav 차단 우회 probe 스크립트 삭제`

### Task 5: SSH locale 경고 차단 (`SetEnv=LC_ALL=C`)

**Files:**
- Modify: `src/meridian_x/remote.py:184-190` (`run_remote_ssh`의 cmd 리스트)
- Test: `tests/test_remote.py` (기존 assertion 갱신 + 신규)

**Interfaces:**
- Consumes: 없음
- Produces: 모든 `run_remote_ssh` 호출(classify/tidy의 `_ssh`)이 경고 없는 stdout을 반환

- [ ] **Step 1: 실패 테스트 작성/갱신** — `test_run_remote_ssh_execution`의 args assertion에 `"SetEnv=LC_ALL=C"` 추가, 그리고 별도 케이스:

```python
def test_run_remote_ssh_sets_locale_env():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="OK\n", stderr="")
        run_remote_ssh("nas.host", "ls", user="media")
        args = mock_run.call_args[0][0]
        assert "SetEnv=LC_ALL=C" in args
```

dry_run 경로(`test_run_remote_ssh_dry_run`)는 cmd 생성 안 하므로 변경 없음.

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_remote.py -v -k locale` → FAIL
- [ ] **Step 3: 구현** — cmd 리스트에 `"-o", "SetEnv=LC_ALL=C"` 추가 (2026-11-14 실측: `-o SendEnv=`은 문법 오류, `SetEnv=LC_ALL=C`만 경고 제거 확인)
- [ ] **Step 4: 통과 확인** — `uv run pytest tests/test_remote.py -v` → 전부 PASS
- [ ] **Step 5: 실측 검증** — `ssh -o ConnectTimeout=5 -o SetEnv=LC_ALL=C media@100.96.115.19 'echo OK'` → 경고 라인 없이 `OK`만 출력
- [ ] **Step 6: Commit** — `git add src/meridian_x/remote.py tests/test_remote.py` → `fix(remote): SSH 세션 LC_ALL=C 고정으로 locale 경고 및 출력 오염 제거`

### Task 6: config 예시·실설정·문서 반영

**Files:**
- Modify: `config/settings.json.example` (sources.onejav에 `"favorite_url": null` 추가)
- Modify: `config/settings.json` (실제 token URL — **gitignored, 커밋 대상 아님**)
- Modify: `config/settings.json.sops` (재암호화)
- Modify: `docs/okf/reference/configuration.md` (favorite_url 항목 1줄)

**Interfaces:**
- Consumes: Task 1의 config key `sources.onejav.favorite_url`
- Produces: 운영 설정에서 favorite 수집 활성화

- [ ] **Step 1: example 갱신** — `sources.onejav` 블록에 `"favorite_url": null` 추가 후 Commit 대상으로 staging
- [ ] **Step 2: 실설정 반영** — `config/settings.json`의 `sources.onejav`에 token URL 추가. **token 값은 이 문서에 기입 금지 — 실행 시 사용자에게 요청해 받는다**
- [ ] **Step 3: sops 재암호화** — `sops --encrypt --input-type binary --output-type binary config/settings.json > config/settings.json.sops` 후 `sops --decrypt config/settings.json.sops | grep -c favorite_url`로 1 확인 (복호화 출력에 token이 찍히지 않도록 grep -c만)
- [ ] **Step 4: 문서** — `configuration.md`의 onejav 소스 섹션에 favorite_url 설명 1줄 (token URL은 sops 관리 대상 명시)
- [ ] **Step 5: Commit** — example + 문서 + sops: `git add config/settings.json.example config/settings.json.sops docs/okf/reference/configuration.md` → `docs(config): onejav favorite_url 설정 추가`

### Task 7: 전체 회귀 + e2e dry-run

**Files:** 없음 (검증만)

- [ ] **Step 1: 전체 회귀** — `uv run pytest tests/ -v` → 전부 PASS (기존 189 passed 2 skipped 기준, 신규 ~10개 추가)
- [ ] **Step 2: e2e dry-run** — `uv run meridian transmission --source onejav --dry-run` → RSS 30개 + `[favorite] N items` 로그와 함께 favorite 항목 나열, 이미 받은 품번은 history로 skip
- [ ] **Step 3: locale 부작용 확인** — dry-run 로그에 `setlocale` 경고 문자열 0건 (`grep -c setlocale logs/<오늘>/*.log`)
- [ ] **Step 4: 최종 Commit** — 잔여 변경 있으면 `chore: 회귀 검증 후 정리` (보통 없음)

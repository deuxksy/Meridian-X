# onejav favorite 수집 + 사용하지 않는 기능 정리 — 설계

> Date: 2026-11-14
> Status: 승인 대기
> Size: Small change

## 배경

로그 기반(391개, 2026-08~11) 미사용 기능 조사에서 출발. `--favorite` 플래그는 6월 multi-source 전환(5ebb643) 이후 죽은 코드로 확인됨. 사용자가 실제 onejav 즐겨찾기 URL(token 기반, 비로그인)을 제공했고, 해당 페이지가 HTML에 직접 `.torrent` 링크를 포함함을 확인해 config 기반 수집 기능으로 부활하기로 함.

## 목표

1. onejav 즐겨찾기(사용자가 등록한 배우/tag 신작)를 정기 수집에 포함
2. `--favorite` dead flag 제거
3. `scripts/probe_onejav_gate.py`, `scripts/probe_onejav_ech.py` 삭제
4. setlocale SSH 버그 수정(원격 locale 경고가 출력 파싱에 섞이는 문제)

## 비목표

- 독립 서브커맨드 `filter`/`label`/`sync`는 유지(제거 안 함 — 디버깅용 단독 경로)
- `--lookup-jav`는 유지(정상 작동 확인됨)
- favorite의 FHD 필터/dedup 적용 — 즐겨찾기는 사용자 명시적 선택이므로 무조건 수집

## 접근 (Approaches)

favorite 수집 3안 검토:

| 안 | 내용 | 판단 |
| :- | :--- | :--- |
| 1. config 병행 (채택) | `sources.onejav.favorite_url` 추가, RSS 수집과 병행 | 자동화 자연스러움, token이 sops 관리 대상 |
| 2. CLI 플래그 복원 | `--favorite <URL>` 수동 실행 | 매번 긴 token URL 붙여넣기 + shell history 노출 |
| 3. rss_url 대체 | 기존 RSS를 favorite으로 교체 | HTML이라 파서 교체 필요 + 전체 RSS 수집 상실 |

구현 구조: `discover()` 내부 병합이 아니라 `discover_favorite()` 분리 — favorite 항목에 소스 내부 필터가 상속되지 않게 하고, collect.py는 `hasattr`로 병합(향후 타 소스 확장 가능).

## 설계 상세

- **config**: `sources.onejav.favorite_url`(선택, 기본 null). example에 null 예시 추가. 실제 token URL은 `settings.json`(sops 추적본 재암호화)
- **`onejav.discover_favorite(config)`**: FlareSolverr로 favorite 페이지 fetch 1회 → 기존 `DOWNLOAD_HREF_RE`로 `.torrent` 링크 추출 → item `{id: "onejav:<CODE>", title: <CODE>, download_url, cookies, user_agent}`. CODE는 URL 경로(`/torrent/<code>/download/...`)에서 추출·대문자화 — 기존 RSS item ID 규칙과 동일해 history dedup가 그대로 동작
- **`onejav.resolve()`**: item에 `download_url`이 있으면 페이지 재fetch 생략, discover 시 보관한 `cookies`/`user_agent`로 `download_via_proxy` 즉시 다운로드(FlareSolverr 왕복 1회 절약. cf_clearance는 동일 gluetun egress·UA 바인딩이라 같은 수집 실행 내 유효)
- **collect.py**: `src_module`에 `discover_favorite`가 있으면 items에 병합, 로그로 구분(`[favorite] N items`)
- **cli.py**: `--favorite` 인자 선언 제거
- **scripts**: probe 2종 삭제
- **remote.py**: SSH 원격 명령에 `LC_ALL=C` 고정(또는 ssh `SendEnv` 차단) — ko_KR.UTF-8 경고 근절, phantom 파일명 오염 방지. 세부 방식은 구현 시 remote.py 구조에 맞게 선택
- **테스트**: `_parse_favorite` HTML fixture, `resolve()` download_url bypass, `--favorite` 제거 후 CLI 회귀, setlocale prefix 반영 여부

## 제품 판단 (사용자 결정 사항)

- favorite은 필터 없이 무조건 수집 — 페이지에 나오는 것은 사용자가 등록한 배우/tag뿐
- favorite item의 title은 품번 사용(카드 제목 추출 불가) — 표시용이므로 무해

## 남는 구현 판단 (builder 재량)

- `_parse_favorite`의 title/메타 정보 보강 여부
- setlocale 수정의 정확한 위치(remote.py 명령 prefix vs ssh 옵션)

# Meridian-X Common Agent Rules (Single Source of Truth)

프라이빗 미디어 컬렉션 자동 수집, 정리, 분류, 메타데이터 및 Jellyfin 동기화 자동화 스위트. 모든 AI runtime은 이 파일을 공통 프로젝트 instruction의 기준으로 사용한다.

웹 화보 및 단축링크 우회/직링크 추출은 자매 프로젝트 `Vesper-X`로 분리 관리한다.

## Commands

```bash
# Setup
uv sync
cp config/settings.json.example config/settings.json
# 또는 sops 추적본 복원
sops --decrypt --input-type binary --output-type binary config/settings.json.sops > config/settings.json
# settings.json 변경 후 암호화 추적본 갱신
sops --encrypt --input-type binary --output-type binary config/settings.json > config/settings.json.sops

# Tests
uv run pytest tests/ -v

# 의존성 업그레이드 시 requirements.txt 동기화 (CI pip-audit / Dependabot 스캔 대상)
uv pip compile --upgrade pyproject.toml -o requirements.txt
```

## Architecture

프로젝트 구조는 `README.md` 또는 [아키텍처 & 워크플로우](../docs/okf/explanation/architecture-and-workflow.md) 참조.

## Configuration

- `pyproject.toml`: Python 3.12+, hatchling build, `meridian` console script.
- `config/settings.json`: 메인 설정. gitignored. 최상위 `proxy`(gluetun HTTP proxy URL)는 전 소스 fetch 우회에 사용한다.
- `config/settings.json.example`: 설정 템플릿.
- `config/settings.json.sops`: sops+age 암호화 추적본.
- `~/.config/meridian-x/credentials.json`: 선택 사용자 인증 override (XDG). `load_config()`가 deep merge로 우선 적용한다.
- `.env`: 선택 환경변수. gitignored. API key/토큰 평문 커밋 금지.
- `data/meridian.db`: SQLite 저장소. `download_history`, `jav_metadata`, `west_metadata`, `actresses`, `retention_stats` 테이블 사용.

## Key Patterns

- **Config 로딩**: `meridian_x.core.load_config()` 사용.
- **History 관리**: `MeridianDB`가 `{source}:{id}` 형식으로 중복 수집을 방지한다.
- **Transmission RPC**: `TransmissionClient`가 add/filter/label/stop-after-download 흐름을 관리한다.
- **Pipeline 순서**: `stop → filter → label → sync → tidy → classify → Jellyfin refresh → report`.
- **tidy → classify 순서 유지**: tidy가 flatten/파일명 정리 후 classify가 배우/스튜디오/장르/JPN/FC2/West로 분류한다. 배우 폴더명은 영문(`First Last`)을 표준으로 하고 한자·가나 표기는 `classify.artist_aliases`로 매핑한다.
- **JAV 메타데이터**: FANZA → JavBus/Jav321 → OneJAV 순서로 필드 단위 병합 후 DB 캐시.
- **West 메타데이터**: StashDB GraphQL API 조회 후 배우/스튜디오/태그를 Jellyfin 및 분류에 사용.
- **화질 필터링 & 취향 스코어링**: 모든 미디어 소스는 `is_fhd_or_higher()` 및 `deduplicate_releases()`로 FHD(1080p) 및 `WRB`/`XC`를 선별한 뒤, `run_transmission()`에서 전 소스 후보를 `score_taste()`(`retention_stats` 잔존 스냅샷 + 캐시 메타데이터 + 등록 배우/스튜디오/프리픽스)로 글로벌 정렬하고 `collection.scoring.min_score` 미만은 스킵한다. 단, `meridian favorite`는 필터·스코어링 없이 무조건 수집한다.
- **즐겨찾기 수집**: `meridian favorite` 서브커맨드는 `discover_favorite()` 보유 소스의 `favorite_url`(token URL)만 수동 수집하며 `transmission`(RSS) 수집과 분리돼 있다.
- **원격 SSH 및 프록시 실행**: `meridian_x.remote` 모듈(`run_remote_ssh`, `fetch_remote_curl`, `get_proxies`, `fetch_via_proxy`, `download_via_proxy`)이 원격 SSH 실행과 사이트 접속 우회를 일원화 관리한다. 소스 fetch는 `proxy(brla gluetun) → lt SSH curl → 직접` 순서로 시도한다.
- **문서 구조**: README와 문서 구조는 `docs/README.md`의 Diátaxis 인덱스를 기준으로 유지한다.

## Verification

- 변경 후 우선 관련 테스트를 좁게 실행하고, 필요하면 전체 회귀를 실행한다.
- 원격/외부 시스템 변경 전에는 가능한 dry-run을 먼저 사용한다.

## Gotchas

- `config/settings.json`이 없으면 실행 시 `FileNotFoundError`가 발생한다.
- Transmission RPC는 생성 시점에 세션 핸드셰이크를 수행한다. tailnet 장애 시 timeout이 길어질 수 있어 `_probe_reachable` 경로를 고려한다.
- `filter`/`label --dry-run`은 영향 항목 상세를 나열하지 않고 요약만 출력한다.
- 모든 meridian 명령은 import 시점에 `logs/YYMMDD/hhmmss.log`를 생성할 수 있다.
- Jellyfin 204 응답은 body가 없다. REST helper에서 content 존재 여부를 확인해야 한다.
- heritage 서버는 unprivileged LXC 권한 매핑 때문에 반드시 `media` UID 1000 계정으로 SSH 조작한다.
- Jellyfin은 기동 시 시스템 디스크(`/config/data`) 여유 공간이 2GiB 미만이면 시작을 중단(Caddy 502 유발)하므로, `metadata`/`cache`/`/tmp/jellyfin`은 `/mnt/data2/torrent/jellyfin`으로 분리 마운트한다.
- `sukebei`(및 레거시 `torrentgalaxy`)는 KR 차단 회피를 위해 최상위 `proxy`(brla gluetun, Surfshark Singapore egress) 우선, 실패 시 `sources.<name>.remote.ssh_alias: "lt"` 원격 curl 폴백으로 fetch한다. Sukebei RSS는 `https://sukebei.nyaa.si/xmlns/nyaa` 네임스페이스를 쓰며 `<link>`는 `.torrent`, `<guid>`가 `/view/<id>`다.
- `onejav.com`은 KR 차단목록 등재 + 사이트 전체 Cloudflare JS challenge(`cf-mitigated: challenge`, 403)로 `requests`/`curl`은 IP와 무관하게 막힌다. RSS·페이지는 최상위 `flaresolverr`(brla 컨테이너, `proxy: http://gluetun:8888`)로 받고, `.torrent`는 발급된 `cf_clearance`+UA로 gluetun `proxy` 다운로드한다. `cf_clearance`는 egress IP·UA 바인딩이라 두 경로가 같은 gluetun을 써야 한다.
- FlareSolverr는 RSS를 Chromium XML viewer의 HTML-escape된 `<pre>`로 감싸 반환하므로 `html.unescape()` 후 파싱한다.
- Surfshark exit 노드는 Singapore로 고정한다. Japan exit IP는 onejav가 503으로 거부한다.
- 원격 curl 실패 시 `-s` 플래그가 에러를 삼켜 "empty output"처럼 보인다. 디버깅은 `curl -sS -v`로 한다(error 35 = TLS reset).
- TorrentGalaxy(`torrentgalaxy.one` 및 미러)는 도메인 폐기/응답 불능으로 현재 `settings.json`에서 `enabled: false` 비활성 상태다(코드는 `/get-posts/category:<name>:format:json/` 기준으로 보존).
- tidy shell script 테스트는 `_build_*_script()` 빌더를 로컬 `bash -c`로 검증한다.
- macOS 기본 APFS는 case-insensitive일 수 있어 case-dup 테스트가 skip될 수 있다.

## Roadmap

향후 계획: [ROADMAP.md](../docs/okf/explanation/roadmap.md)

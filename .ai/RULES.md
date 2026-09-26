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

# Tests
uv run pytest tests/ -v
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
- `data/meridian.db`: SQLite 저장소. `download_history`, `jav_metadata`, `west_metadata` 테이블 사용.

## Key Patterns

- **Config 로딩**: `meridian_x.core.load_config()` 사용.
- **History 관리**: `MeridianDB`가 `{source}:{id}` 형식으로 중복 수집을 방지한다.
- **Transmission RPC**: `TransmissionClient`가 add/filter/label/stop-after-download 흐름을 관리한다.
- **Pipeline 순서**: `stop → filter → label → sync → tidy → classify → Jellyfin refresh → report`.
- **tidy → classify 순서 유지**: tidy가 flatten/파일명 정리 후 classify가 배우/스튜디오/장르/JPN/FC2/West로 분류한다.
- **JAV 메타데이터**: FANZA → JavBus/Jav321 → OneJAV 순서로 필드 단위 병합 후 DB 캐시.
- **West 메타데이터**: StashDB GraphQL API 조회 후 배우/스튜디오/태그를 Jellyfin 및 분류에 사용.
- **화질 필터링 & 중복 선별**: 모든 미디어 소스는 `is_fhd_or_higher()` 및 `deduplicate_releases()`를 통해 FHD(1080p) 및 안정적 릴 그룹(`WRB`/`XC`)을 최우선 선별한다.
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
- `onejav`, `sukebei`, `torrentgalaxy`는 KR 차단 회피를 위해 최상위 `proxy`(brla gluetun, Surfshark Singapore egress) 우선, 실패 시 `sources.<name>.remote.ssh_alias: "lt"` 원격 curl 폴백으로 fetch한다.
- `onejav.com`은 한국 차단목록 등재로 KR egress(lt, heritage 전부)에서 TLS RST/URL 차단된다. lt 경유 성공은 우연에 의존하므로 프록시가 필수다.
- Surfshark exit 노드는 Singapore로 고정한다. Japan exit IP는 onejav가 503으로 거부한다.
- 원격 curl 실패 시 `-s` 플래그가 에러를 삼켜 "empty output"처럼 보인다. 디버깅은 `curl -sS -v`로 한다(error 35 = TLS reset).
- TorrentGalaxy는 2026-08 플랫폼 마이그레이션으로 `/rss?cat=<id>`와 `torrents.php`를 폐기했다 (302 → homepage). discover는 `/get-posts/category:XXX:format:json/` JSON API를 사용하며, 카테고리는 숫자 ID가 아닌 이름(`category:<name>`)으로 지정한다.
- tidy shell script 테스트는 `_build_*_script()` 빌더를 로컬 `bash -c`로 검증한다.
- macOS 기본 APFS는 case-insensitive일 수 있어 case-dup 테스트가 skip될 수 있다.

## Roadmap

향후 계획: [ROADMAP.md](../docs/okf/explanation/roadmap.md)

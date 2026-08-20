# Meridian-X Common Agent Rules (Single Source of Truth)

프라이빗 미디어 컬렉션 자동 수집, 정리, 분류, 메타데이터 및 Jellyfin 동기화 자동화 스위트. 모든 AI runtime은 이 파일을 공통 프로젝트 instruction의 기준으로 사용한다.

## Commands

```bash
# Setup
uv sync
cp config/settings.json.example config/settings.json
# 또는 sops 추적본 복원
sops --decrypt --input-type binary --output-type binary config/settings.json.sops > config/settings.json

# Meridian Pipeline Commands
uv run meridian transmission --dry-run
uv run meridian transmission
uv run meridian transmission --source onejav
uv run meridian transmission --source sukebei
uv run meridian transmission --source xxxclub
uv run meridian transmission --source torrentgalaxy
uv run meridian filter
uv run meridian label
uv run meridian sync
uv run meridian search "Dakota Doll" --category 1080p
uv run meridian search "Dakota Doll" --auto --delay 5
uv run meridian search "MINAMO" --source sukebei
uv run meridian search "Angela White" --source tgx
uv run meridian tidy --dry-run
uv run meridian tidy
uv run meridian classify --dry-run
uv run meridian classify
uv run meridian classify --no-lookup
uv run meridian classify --lookup-jav
uv run meridian pipeline --dry-run
uv run meridian pipeline
uv run meridian pipeline --no-refresh
uv run meridian report

# Tests
uv run pytest tests/ -v
```

## Architecture

```text
src/
└── meridian_x/
    ├── cli.py            # CLI 진입점 (classify, filter, label, pipeline, report, search, sync, tidy, transmission)
    ├── collect.py        # Multi-source 수집 오케스트레이터
    ├── sources/          # onejav, sukebei, xxxclub, torrentgalaxy source 모듈
    ├── transmission.py   # Transmission RPC 클라이언트
    ├── jellyfin.py       # Jellyfin REST API 클라이언트
    ├── tidy.py           # 원격 파일 정리 (SSH)
    ├── classify.py       # 원격 파일 분류 (SSH)
    ├── report.py         # disk/토렌트 상태 리포트
    ├── db.py             # SQLite 저장소(download_history, jav_metadata, west_metadata)
    ├── fanza.py          # FANZA API 클라이언트
    ├── jav_lookup.py     # JavBus/Jav321 및 OneJAV SSH 조회
    ├── jav_metadata.py   # JAV 메타데이터 통합 Resolver + DB 캐시
    ├── west_metadata.py  # StashDB GraphQL API Resolver + DB 캐시
    └── core.py           # 설정/히스토리/화질필터/중복선별 공통 함수
```

## Configuration

- `pyproject.toml`: Python 3.12+, hatchling build, `meridian` console script.
- `config/settings.json`: 메인 설정. gitignored.
- `config/settings.json.example`: 설정 템플릿.
- `config/settings.json.sops`: sops+age 암호화 추적본.
- `.env`: 선택 환경변수. gitignored. API key/토큰 평문 커밋 금지.
- `meridian.db`: SQLite 저장소. `download_history`, `jav_metadata`, `west_metadata` 테이블 사용.

## Key Patterns

- **Config 로딩**: `meridian_x.core.load_config()` 사용.
- **History 관리**: `MeridianDB`가 `{source}:{id}` 형식으로 중복 수집을 방지한다.
- **Transmission RPC**: `TransmissionClient`가 add/filter/label/stop-after-download 흐름을 관리한다.
- **Pipeline 순서**: `stop → filter → label → sync → tidy → classify → Jellyfin refresh → report`.
- **tidy → classify 순서 유지**: tidy가 flatten/파일명 정리 후 classify가 배우/스튜디오/장르/JPN/FC2/West로 분류한다.
- **JAV 메타데이터**: FANZA → JavBus/Jav321 → OneJAV 순서로 필드 단위 병합 후 DB 캐시.
- **West 메타데이터**: StashDB GraphQL API 조회 후 배우/스튜디오/태그를 Jellyfin 및 분류에 사용.
- **화질 필터링 & 중복 선별**: 모든 미디어 소스는 `is_fhd_or_higher()` 및 `deduplicate_releases()`를 통해 FHD(1080p) 및 안정적 릴 그룹(`WRB`/`XC`)을 최우선 선별한다.

## Verification

- 변경 후 우선 관련 테스트를 좁게 실행하고, 필요하면 전체 회귀를 실행한다.
- 원격/외부 시스템 변경 전에는 가능한 dry-run을 먼저 사용한다.
- 대표 검증:
  - `uv run pytest tests/test_db.py -v`
  - `uv run pytest tests/test_core.py -v`
  - `uv run pytest tests/test_sukebei.py tests/test_torrentgalaxy.py -v`
  - `uv run pytest tests/ -v`

## Gotchas

- `config/settings.json`이 없으면 실행 시 `FileNotFoundError`가 발생한다.
- Transmission RPC는 생성 시점에 세션 핸드셰이크를 수행한다. tailnet 장애 시 timeout이 길어질 수 있어 `_probe_reachable` 경로를 고려한다.
- `filter`/`label --dry-run`은 영향 항목 상세를 나열하지 않고 요약만 출력한다.
- 모든 meridian 명령은 import 시점에 `logs/YYMMDD/hhmmss.log`를 생성할 수 있다.
- Jellyfin 204 응답은 body가 없다. REST helper에서 content 존재 여부를 확인해야 한다.
- heritage 서버는 unprivileged LXC 권한 매핑 때문에 반드시 `media` UID 1000 계정으로 SSH 조작한다.
- `onejav`, `sukebei`, `torrentgalaxy`는 ISP/Cloudflare 차단 회피를 위해 `sources.<name>.remote.ssh_alias: "lt"` 경유 원격 curl을 사용한다.
- tidy shell script 테스트는 `_build_*_script()` 빌더를 로컬 `bash -c`로 검증한다.
- macOS 기본 APFS는 case-insensitive일 수 있어 case-dup 테스트가 skip될 수 있다.

## Roadmap

향후 계획: [ROADMAP.md](../ROADMAP.md)

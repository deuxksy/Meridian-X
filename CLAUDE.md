# Meridian-X

미디어 컬렉션 자동화 큐레이션 도구. RSS 수집 → 정제 → 분류 파이프라인.

## Commands

```bash
# ========== Setup (초기 설정) ==========
uv sync                              # 의존성 설치
cp config/settings.json.example config/settings.json  # 설정 파일 복사
# .env 파일에 FANZA_API_ID, FANZA_AFFILIATE_ID 설정 (선택)

# ========== Collect (Transmission RPC) ==========
uv run meridian transmission                     # RSS → Transmission RPC 전송
uv run meridian transmission --dry-run            # 미리보기
uv run meridian transmission --max-downloads 30    # 최대 30개 (전체 source 합산)
uv run meridian transmission --source onejav       # onejav만
uv run meridian transmission --source xxxclub      # xxxclub만

# ========== Filter (기존 토렌트 필터링) ==========
uv run meridian filter                          # 전체 토렌트 광고 파일 제외

# ========== Label (기존 토렌트 라벨링) ==========
uv run meridian label                           # 메이커/배우 labels 자동 설정

# ========== Sync (Transmission → Jellyfin) ==========
uv run meridian sync                            # Transmission labels → Jellyfin Tags 동기화

# ========== Tidy (원격 파일 정리) ==========
uv run meridian tidy                            # 정크삭제→Flatten→파일명정리→라이브러리갱신

# ========== Classify (원격 분류, tidy 후 실행) ==========
uv run meridian classify --dry-run                # 미리보기 (항상 먼저)
uv run meridian classify                          # SSH로 원격 파일 분류

# ========== Pipeline (한 번에 실행, transmission 제외) ==========
uv run meridian pipeline --dry-run              # 미리보기 (항상 먼저)
uv run meridian pipeline                        # filter → label → sync → tidy → classify

# ========== Verification ==========
uv run meridian transmission --dry-run          # 항상 --dry-run으로 먼저 확인
```

## Architecture

```text
src/meridian_x/
├── cli.py            # CLI 진입점 (classify, filter, label, pipeline, sync, tidy, transmission)
├── classify.py        # 원격 파일 분류 (SSH 하이브리드: Python 매칭 + mv)
├── collect.py        # Multi-source orchestrator (source 순회, history 관리)
├── sources/          # Source 모듈 (discover + resolve 함수)
│   ├── onejav.py     # OneJAV SSH 경유 (Cloudflare 우회): RSS → 페이지 → .torrent
│   └── xxxclub.py    # XXXClub RSS → magnet link 직접 추출
├── transmission.py    # Transmission RPC 클라이언트 (add/filter/label)
├── jellyfin.py       # Jellyfin REST API 클라이언트 (sync tags, refresh library)
├── tidy.py           # 원격 파일 정리 (정크삭제→Flatten→파일명정리→갱신)
├── fanza.py          # FANZA API 클라이언트 (JAV 메타데이터 조회, 보존됨/classify 미사용)
└── core.py           # 공통 함수 (설정 로드, RSS 파싱, 히스토리 관리)
```

## Configuration

- `config/settings.json` — 메인 설정 (gitignored). `settings.json.example` 참고.
- `.env` — FANZA API: `FANZA_API_ID`, `FANZA_AFFILIATE_ID`
- `jellyfin.api_key` — Jellyfin API Key (settings.json에 직접 설정)
- 로그: `logs/YYMMDD/hhmmss.log`

## Key Patterns

- **Config 로딩**: `core.load_config()` 사용
- **Transmission RPC**: `transmission.py`의 `TransmissionClient` (paused 추가 → 파일 필터링 → labels → start)
- **Labels**: torrent name에서 자동 추출 (소문자)
  - JAV: 메이커 코드 (`SNOS-125` → `['snos']`, `FC2-PPV-4895410` → `['fc2']`)
  - West: 스튜디오 + 배우 (`Vixen.16.09.06.Lily.Love...` → `['vixen', 'lily love']`)
- **파일 필터**: 확장자/키워드/최소 크기로 광고 파일 자동 제외 (settings.json `filters`)
- **Multi-source**: `sources/` 패키지의 각 모듈이 `discover()`+`resolve()` 제공. `collect.py`가 활성 source 순회.
- **History ID**: `{source}:{id}` 형태 (`onejav:SNOS155`, `xxxclub:<infohash>`). prefix 없는 기존 항목은 `onejav:` 자동 부여(migration).
- **분류 우선순위** (classify): 배우(`artist_folders`) > 스튜디오(`studio_folders`) > 장르(`genres`) > JAV 패턴(`JPN/`) > FC2(`FC2/`) > West(fallback). tidy(flatten) 후 실행.
- **JAV 패턴**: `^[A-Z0-9]{3,7}-\d{2,5}[-\.\s]` (예: SONE-446, 200GANA-3399, 300MIUM-1383) → `JPN/`
- **FC2 패턴**: `^FC2` (예: FC2-PPV-4914752) → `FC2/`

## Gotchas

- `config/settings.json` 없으면 `FileNotFoundError` 발생. 최초 설정 시 example 복사 필수.
- Transmission RPC 사용 시 `config/settings.json`에 `transmission.rpc_url` 설정 필수.
- Transmission 409 응답 = CSRF 세션 ID 요구 (인증 에러 아님, 자동 처리됨).
- `labels` 필드 (RPC spec) 미지원 빌드 → `labels` 사용 (linuxserver/transmission).
- 토렌트 추가 흐름: `paused` → `torrent-set`(labels) → `torrent-set`(files-unwanted) → `torrent-start`.
- Duplicate 토렌트는 filter/labels 적용 안 됨 (`torrent-added` 응답이 아니므로).
- `filter`/`label --dry-run`은 대상 항목을 나열하지 않고 "Would filter/label all torrents"만 출력. 영향받는 항목 사전 확인 불가.
- 모든 명령은 import 시점에 `logs/YYMMDD/hhmmss.log`를 자동 생성 (`--dry-run` 포함).
- Jellyfin `POST /Items/{id}` 시 Fields 파라미터에 Genres, Studios 등 필수. 누락 시 .ToList()에서 ArgumentNullException 발생.
- Jellyfin 204 응답은 body 없음. `_post()`에서 content 체크 필수.
- heritage 서버 (Proxmox CT 200, **unprivileged LXC**, Debian 12): SSH `media@100.96.115.19` (Tailscale, UID 1000). walle = Proxmox 클러스터 호스트. 미디어 경로: `/mnt/data1/torrent/complete` (Transmission `/downloads/complete`, Jellyfin `/data2` 마운트).
- heritage 권한 매핑 (핵심): unprivileged LXC + `/mnt/data1` raw bind mount (idmap 없음) → 컨테이너 root(0)=호스트 100000 매핑, UID 1000 파일 mv/rm 차단 (`Permission denied`). Transmission/Jellyfin 모두 `PUID=1000 PGID=1000`. **반드시 `media`(UID 1000) 계정으로 SSH** (settings.json `remote.user`). root SSH 사용 금지.
- onejav Cloudflare 차단: girl IP가 반복 요청 시 rate 차단 (Connection reset). SSH 경유(heritage `curl -sL`)로 우회. `-L` 필수 (http→https redirect). RSS/페이지/.torrent 전부 heritage curl, 바이너리는 `base64` 경유.
- 워크플로우: `tidy`(정리/flatten) → `classify`(분류). tidy가 폴더 flatten 후 classify가 파일을 배우/장르/스튜디오/JPN/West로 분류. 둘 다 SSH 기반 (로컬 실행 + 원격 조작).
- classify는 tidy 실행 후 호출 권장 (flatten되지 않은 파일은 분류 안 됨).

## Roadmap

향후 계획: [ROADMAP.md](ROADMAP.md)

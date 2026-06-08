# Meridian-X

미디어 컬렉션 자동화 큐레이션 도구. RSS 수집 → 정제 → 분류 파이프라인.

## Commands

```bash
# ========== Setup (초기 설정) ==========
uv sync                              # 의존성 설치
cp config/settings.json.example config/settings.json  # 설정 파일 복사
# .env 파일에 FANZA_API_ID, FANZA_AFFILIATE_ID 설정 (선택)

# ========== Collect (다운로드) ==========
uv run meridian collect                       # 로컬 다운로드 (기본)
uv run meridian collect --backend transmission  # Proxmox Transmission RPC
uv run meridian collect --backend transmission --dry-run  # 미리보기
uv run meridian collect --max-downloads 50       # 최대 50개
uv run meridian collect --favorite URL            # Favorite 필터링

# ========== Classify (분류) ==========
uv run meridian classify                          # 분류 실행
uv run meridian classify --dry-run                # 미리보기
uv run meridian classify --jav-metadata            # FANZA 메타데이터 기반 분류

# ========== Verification ==========
uv run meridian collect --dry-run                # 항상 --dry-run으로 먼저 확인
```

## Architecture

```text
src/meridian_x/
├── cli.py            # CLI 진입점
├── classify.py        # 파일 정제 + 우선순위 분류 (배우→장르→스튜디오→JAV→West)
├── collect.py        # 로컬 다운로드 + Transmission RPC
├── transmission.py    # Transmission RPC 클라이언트 (디스크 캐싱, rate limiting)
├── fanza.py          # FANZA API 클라이언트 (JAV 메타데이터 조회, 캐시)
└── core.py           # 공통 함수 (설정 로드, RSS 파싱, 히스토리 관리)
```

## Configuration

- `config/settings.json` — 메인 설정 (gitignored). `settings.json.example` 참고.
- `.env` — FANZA API: `FANZA_API_ID`, `FANZA_AFFILIATE_ID`
- 로그: `logs/YYMMDD/hhmmss.log`

## Key Patterns

- **Config 로딩**: `core.load_config()` 사용
- **다운로드 백엔드**: `--backend` 옵션 (local/transmission)
- **Transmission RPC**: `transmission.py`의 `TransmissionClient` 사용
- **분류 우선순위**: 배우 > 장르 > 스튜디오 > JAV 패턴 > West(fallback)
- **JAV 패턴**: `^[A-Z]{3,5}-\d{3,5}` (예: SONE-446, ABC-001)

## Testing

**항상 `--dry-run`으로 먼저 확인:**
```bash
uv run meridian collect --dry-run          # 다운로드 미리보기
uv run meridian collect --backend transmission --dry-run  # Transmission RPC 미리보기
uv run meridian classify --dry-run        # 분류 미리보기
uv run meridian classify --jav-metadata --dry-run  # JAV 메타데이터 분류 미리보기
```

**로그 확인:** `logs/YYMMDD/hhmmss.log`에서 상세 로그 확인

## Gotchas

- `config/settings.json` 없으면 `FileNotFoundError` 발생. 최초 설정 시 example 복사 필수.
- `fanza.py`는 `.env`의 API 자격증명 필요. 없으면 `--jav-metadata` 동작 안 함.
- Transmission RPC 사용 시 `config/settings.json`에 `transmission.rpc_url` 설정 필수.

## Tech Stack

- Python 3.12+, hatchling build
- 패키지 매니저: `uv`
- 의존성: `requests`, `python-dotenv`

# Meridian-X

미디어 컬렉션 자동화 큐레이션 도구. RSS 수집 → 정제 → 분류 파이프라인.

## Commands

```bash
uv run meridian classify              # 분류 실행
uv run meridian classify --dry-run    # 분류 미리보기
uv run meridian classify --jav-metadata  # FANZA 메타데이터 기반 JAV 분류
uv run meridian collect               # RSS 전체 다운로드 (최대 30개)
uv run meridian collect --dry-run     # 다운로드 미리보기
uv run meridian collect --favorite URL  # Favorite 출연자 필터링
uv run meridian collect --max-downloads 50  # 최대 50개
```

## Architecture

```text
src/meridian_x/
├── cli.py        # CLI 진입점, 로깅 설정
├── classify.py   # 파일 정제 + 우선순위 분류 (배우→장르→스튜디오→JAV→West)
├── collect.py    # OneJAV RSS 수집 + 토렌트 다운로드
└── fanza.py      # FANZA API 클라이언트 (JAV 메타데이터 조회, 캐시)
```

## Configuration

- `config/settings.json` — 메인 설정 (gitignored). `settings.json.example` 참고.
- `.env` — FANZA API: `FANZA_API_ID`, `FANZA_AFFILIATE_ID`
- 로그: `logs/YYMMDD/hhmmss.log`

## Key Patterns

- **Config 로딩**: 각 모듈이 `_load_config()`로 `config/settings.json` 직접 로드 (모듈 레벨에서 실행)
- **dry-run**: 모든 변경 작업은 `dry_run` 파라미터로 미리보기 지원. 항상 `--dry-run`으로 먼저 확인.
- **분류 우선순위**: 배우 > 장르 > 스튜디오 > JAV 패턴 > West(fallback)
- **JAV 패턴**: `^[A-Z]{3,5}-\d{3,5}` (예: SONE-446, ABC-001)

## Gotchas

- `config/settings.json` 없으면 `FileNotFoundError` 발생. 최초 설정 시 example 복사 필수.
- `fanza.py`는 `.env`의 API 자격증명 필요. 없으면 `--jav-metadata` 동작 안 함.
- `set_permissions()`는 현재 비활성화 (`return` 즉시 반환).
- `collect.py`와 `classify.py`에 동일한 `_load_config()` 중복 정의됨.

## Tech Stack

- Python 3.12+, hatchling build
- 패키지 매니저: `uv`
- 의존성: `requests`, `python-dotenv`

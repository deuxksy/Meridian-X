# JPN 작품 분류 및 외부 API 메타데이터 연동 설계서

- **작성일**: 2026-08-09
- **상태**: 승인됨 (Approved)
- **대상 모듈**: `src/meridian_x/jav_metadata.py`, `src/meridian_x/classify.py`, `src/meridian_x/jellyfin.py`, `src/meridian_x/fanza.py`

---

## 1. 개요 (Overview)

Meridian-X의 JPN 미디어 파이프라인을 확장하여, JAV 품번(예: `SONE-446`, `FC2-PPV-123456`)이 감지되면 외부 API(FANZA API) 및 웹 소스(OneJAV)를 활용해 배우, 스튜디오(메이커), 장르 메타데이터를 수집합니다. 

이 메타데이터를 바탕으로 **원격 디렉토리 자동 분류**(`Actors/{배우명}/` 또는 `{스튜디오명}/`)와 **Jellyfin 라이브러리 메타데이터/태그 자동 동기화**(`Studios`, `Genres`, `People`, `Tags`)를 수행합니다.

---

## 2. 모듈 아키텍처 및 메타데이터 스키마 (`jav_metadata.py`)

### 2.1 FANZA 표준 데이터 스키마
FANZA(DMM) Affiliate API 응답 구조를 표준으로 채택합니다.

```python
{
    "code": "SONE-446",
    "actresses": ["MINAMO"],           # 배우 명칭 리스트 (FANZA iteminfo.actress)
    "makers": ["S1 NO.1 STYLE"],       # 스튜디오/메이커 명칭 리스트 (FANZA iteminfo.maker)
    "genres": ["単体作品", "ハイビジョン"], # 장르 명칭 리스트 (FANZA iteminfo.genre)
    "title": "...",                    # 작품 제목 (FANZA item.title 또는 None)
    "cover_url": "https://...",        # 커버 이미지 URL (FANZA item.imageURL.large 또는 None)
    "source": "fanza"                  # 조회 출처 ("fanza" | "onejav" | "cache")
}
```

### 2.2 하이브리드 메타데이터 수집 및 캐싱 흐름
1. **디스크 캐시 검사**: `logs/jav_metadata_cache.json`에서 `code` 조회. 존재 시 즉시 반환.
2. **1차 시도 (FANZA API)**:
   - FC2 품번이 아닌 경우 `FanzaClient.fetch_metadata(code)` 실행.
   - FANZA API ID / Affiliate ID 인증 성공 및 응답 수신 시, FANZA 스키마 형태로 정제 후 디스크 캐시에 저장.
3. **2차 시도 (OneJAV SSH Lookup)**:
   - FANZA API 미조회 건 또는 FC2 품번인 경우 SSH curl 기반 `lookup_jav_actresses(code)` 실행.
   - 파싱한 배우/태그 데이터를 FANZA 표준 스키마 형태로 변환하여 캐시 저장 후 반환.
4. **조회 실패 시**: 빈 스키마 객체 (`{"actresses": [], "makers": [], "genres": [], ...}`) 생성 후 캐싱.

---

## 3. 원격 디렉토리 자동 분류 로직 (`classify.py`)

### 3.1 분류 목적지 결정 우선순위
1. **사용자 명시적 설정 매칭**: `config.json`의 `classify.artists` / `classify.studios`에 등록된 배우/스튜디오명이 파일명에 일치하는 경우 최우선 이동.
2. **외부 API 메타데이터 매칭 (신규)**:
   - JAV 품번 패턴 매칭 시 `jav_metadata.get_metadata(code)` 실행.
   - **(A) 배우 정보 존재 (`actresses` non-empty)**:
     - `actresses[0]` 대표 배우 추출 → `Actors/{배우명}/` 디렉토리로 이동.
   - **(B) 배우 정보 미존재 & 스튜디오 정보 존재 (`makers` non-empty)**:
     - `makers[0]` 대표 스튜디오 추출 → `{스튜디오명}/` (West/JPN 공통 루트 디렉토리 규칙)로 이동.
3. **Fallback**: 기존과 동일하게 `JPN/` (또는 FC2의 경우 `FC2/`) 디렉토리로 이동.

### 3.2 CLI 및 안전성 검증
- `uv run meridian classify`: 메타데이터 조회가 기본으로 수행됨.
- `--no-lookup`: 외부 API 조회를 건너뛰고 단순 품번 매칭 분류만 수행.
- `--dry-run`: 실제 SSH `mv` 명령 없이 예상 이동 경로 (`[Dry-run JAV Lookup] JPN/SONE-446.mp4 -> Actors/MINAMO/`)를 상세 출력.

---

## 4. Jellyfin 메타데이터 & 태그 동기화 (`jellyfin.py`)

### 4.1 Jellyfin REST API 클라이언트 확장
`JellyfinClient`의 `update_tags`를 확장하거나 `update_metadata` 메소드를 추가하여 다음 필드를 동시에 업데이트합니다:
- **`Studios`**: `[{"Name": m} for m in makers]`
- **`Genres`**: `genres` 리스트
- **`People`**: `[{"Name": a, "Type": "Actor"} for a in actresses]`
- **`Tags`**: 배우 및 메이커 명칭의 소문자 태그

### 4.2 Sync 흐름 연동
`uv run meridian sync` 실행 시:
1. Transmission 완료 토렌트 및 Jellyfin 비디오 목록 로드.
2. JAV 품번에 해당하는 비디오 아이템에 대해 `jav_metadata.get_metadata(code)` 조회.
3. Jellyfin `POST /Items/{id}`를 통해 `Studios`, `Genres`, `People`, `Tags` 업데이트.
4. 업데이트 완료 후 `refresh_library()`로 Jellyfin 스캔 트리거.

---

## 5. 테스트 및 검증 계획 (Verification)

1. **단위 테스트 (`pytest`)**:
   - `tests/test_jav_metadata.py`: 캐시 로드/저장, FANZA API 응답 파싱, OneJAV fallback 시뮬레이션 테스트.
   - `tests/test_classify.py`: 메타데이터 기반 `Actors/{배우}` 및 `{스튜디오}` 목적지 경로 계산 테스트.
   - `tests/test_jellyfin.py`: `update_metadata` Payload 생성 및 Jellyfin API 갱신 로직 Mock 테스트.
2. **시뮬레이션 검증**:
   - `uv run meridian classify --dry-run`으로 실제 원격 SSH 실행 없이 분류 동작 검증.

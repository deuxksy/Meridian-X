# StashDB West 미디어 자동 분류 및 메타데이터 연동 설계서

- **작성일**: 2026-08-09
- **상태**: 승인됨 (Approved)
- **대상 모듈**: `src/meridian_x/west_metadata.py`, `src/meridian_x/classify.py`, `src/meridian_x/jellyfin.py`

---

## 1. 개요 (Overview)

Meridian-X의 미디어 파이프라인을 확장하여, West(해외) 미디어 파일명이 감지되면 **StashDB GraphQL API**(`https://stashdb.org/graphql`)를 활용해 Performer(배우), Studio(스튜디오), Tags, Title 메타데이터를 자동 수집합니다.

이 메타데이터를 바탕으로 **West 원격 디렉토리 자동 분류**(`Actors/{Performer}/` 또는 `{Studio}/`)와 **Jellyfin 라이브러리 메타데이터/태그 자동 동기화**(`Studios`, `People`, `Tags`)를 수행합니다.

---

## 2. 모듈 아키텍처 및 메타데이터 스키마 (`west_metadata.py`)

### 2.1 StashDB 표준 데이터 스키마
StashDB GraphQL API (`searchScene`) 응답 구조를 기반으로 데이터 스키마를 정의합니다.

```python
{
    "query_term": "Vixen Lily Love",
    "performers": ["Lily Love"],       # StashDB performers[].performer.name
    "studio": "Vixen",                 # StashDB studio.name (또는 None)
    "tags": ["Lesbian", "MILF (30+)"], # StashDB tags[].name
    "title": "...",                    # StashDB scene title (또는 None)
    "date": "2025-01-29",              # StashDB scene release date (또는 None)
    "source": "stashdb"                # ("stashdb" | "cache" | "none")
}
```

### 2.2 인증, 파일명 정제 및 캐싱 흐름
1. **인증 Key 로드**: `.env` 파일의 `STASHDB_API_KEY` 환경변수 또는 `config/settings.json`의 `stashdb.api_key` 사용 (Header: `ApiKey: <token>`).
2. **파일명 검색어 정제 (Cleaning)**:
   - 파일명에서 릴리즈 그룹/해상도/확장자(`1080p`, `720p`, `MP4`, `MKV`, `XXX`, `P2P`, `WRB`, `NBQ` 등) 및 날짜 패턴(`26.08.05`) 제거.
   - 구분 기호(`.`, `_`, `-`)를 공백으로 변환하여 검색어(`term`) 생성.
3. **디스크 캐시 검사**: `logs/stashdb_metadata_cache.json`에서 `query_term` 조회. 존재 시 즉시 반환.
4. **GraphQL API 조회**: `POST https://stashdb.org/graphql`로 `searchScene(term: ...)` 호출.
5. **결과 캐싱**: 수집된 데이터를 캐시에 저장 후 반환.

---

## 3. 원격 디렉토리 자동 분류 로직 (`classify.py`)

### 3.1 West 분류 목적지 결정 우선순위
1. **1순위 (명시적 설정)**: `config.json`의 `classify.artists.WEST` 또는 `classify.studios.WEST`에 등록된 배우/스튜디오명이 파일명에 일치하는 경우 최우선 이동 (예: `Actors/Lily Love/` 또는 `Vixen/`).
2. **2순위 (StashDB GraphQL API)**:
   - JAV / FC2 패턴이 아닌 West 미디어 파일에 대해 `west_metadata.get_west_metadata(filename)` 실행.
   - **Performers(배우) 수집 시**: `performers[0]` 대표 배우 추출 → **`Actors/{배우명}/`** 이동.
   - **Performers 미존재 & Studio(스튜디오) 수집 시**: `studio` 추출 → **`{스튜디오명}/`** (예: `Vixen/`, `Nubile/` 등) 이동.
3. **3순위 (Fallback)**: 기존과 동일하게 **`West/`** 디렉토리로 이동.

### 3.2 CLI 및 안전성 검증
- `uv run meridian classify`: JPN 및 West 메타데이터 조회가 기본으로 수행됨.
- `--no-lookup`: 외부 API 조회를 건너뛰고 단순 수동 규칙 매칭만 수행.
- `--dry-run`: 실제 SSH `mv` 명령 없이 예상 이동 경로 (`[Dry-run StashDB] Vixen.Lily.Love.mp4 -> Actors/Lily Love/`)를 상세 출력.

---

## 4. Jellyfin 메타데이터 & 태그 동기화 (`jellyfin.py`)

### 4.1 Jellyfin REST API 연동
`JellyfinClient`의 `update_metadata`를 활용하여 West 미디어 아이템의 다음 필드를 동기화합니다:
- **`Studios`**: `[{"Name": studio}]` (스튜디오 존재 시)
- **`People`**: `[{"Name": p, "Type": "Actor"} for p in performers]`
- **`Tags`**: StashDB `tags` 리스트 및 배우/스튜디오 태그 병합 (소문자 변환)

### 4.2 Sync 흐름 연동
`uv run meridian sync` 실행 시:
1. Transmission 완료 토렌트 및 Jellyfin 비디오 목록 로드.
2. West 비디오 아이템에 대해 `west_metadata.get_west_metadata(filename)` 조회.
3. Jellyfin `POST /Items/{id}`를 통해 `Studios`, `People`, `Tags` 업데이트.
4. 업데이트 완료 후 `refresh_library()`로 Jellyfin 라이브러리 스캔 트리거.

---

## 5. 테스트 및 검증 계획 (Verification)

1. **단위 테스트 (`pytest`)**:
   - `tests/test_west_metadata.py`: 파일명 정제 로직, StashDB GraphQL API 응답 파싱 및 디스크 캐시 테스트.
   - `tests/test_classify.py`: West 파일에 대한 StashDB 메타데이터 기반 `Actors/{배우}` 및 `{스튜디오}` 목적지 경로 산출 테스트.
   - `tests/test_jellyfin.py`: StashDB 메타데이터 기반 Jellyfin API 갱신 Mock 테스트.
2. **시뮬레이션 검증**:
   - `uv run meridian classify --dry-run`으로 실제 원격 SSH 실행 없이 West 분류 동작 검증.

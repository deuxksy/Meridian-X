# Taste Scoring Design (Approach C: Hybrid Retention-Driven + Shadow Mode)

## Intent & Why
현재 `collect.py`는 RSS 최신순으로 `new_items[:remaining]`을 잘라 수집하므로, `max_count` 내에서 선호 배우·고생존율 스튜디오가 밀리거나 결국 삭제(생존율 26.1%)되는 항목이 먼저 수집된다. 사람이 임의 숫자를 찍지 않고 **실제 디스크에 살아남은 파일 수**를 자동 가중치로 환산하되, 초기에는 차단 없이 정렬·로그 관찰(Shadow)로 시작하고 추후 `min_score` 1줄로 컷오프 전환할 수 있게 한다.

## Goals, Non-Goals, Anti-Goals
- **Goals**
  - `meridian report` 실행 시 원격 잔존 집계(배우·스튜디오별 파일 수)를 `meridian.db`에 스냅샷 저장.
  - `core.py`에 `score_taste(item, config, retention_stats)` 순수 함수 추가: `(score, reasons)` 반환.
  - `collect.py`에서 `new_items`를 `score_taste` 내림차순 정렬(동점 시 기존 RSS 순서 유지)하고, 각 항목의 점수·매칭 사유를 로그에 기록.
  - `settings.json`의 `collection.scoring.min_score`(기본 `0`, 비활성) 설정 시 해당 점수 미만 항목 자동 스킵.
- **Non-Goals**
  - ML/임베딩 기반 추천 모델.
  - `meridian favorite`에 스코어링/컷오프 적용 (즐겨찾기는 명시적 선택이므로 기존대로 무조건 수집).
  - `collect` 실행 중 실시간 원격 SSH 조회 (DB 스냅샷만 사용하여 네트워크 지연·장애 격리).
- **Anti-Goals**
  - `retention_stats` 스냅샷이 비어 있거나 오래되었을 때 수집이 실패하거나 전량 차단되는 동작.

## Approaches Considered
1. **Approach A — 선언적 티어 + 관찰 모드**: 사람이 티어를 수동 분류해야 하며 다운로드 절감 효과가 없음.
2. **Approach B — 실데이터 자동 가중치 + 즉시 차단**: 신규 배우/스튜디오 Cold Start 오탐으로 원하는 작품을 놓칠 위험.
3. **Approach C — 하이브리드 (채택)**: 실제 잔존량 + 등록 바닥 점수로 자동 계산하되, 기본 `min_score=0`(Shadow Ranking + 로그)으로 시작해 검증 후 컷오프 전환.

## Design Summary

### 1. DB 스냅샷 (`src/meridian_x/db.py`)
`retention_stats` 테이블 추가:
```sql
CREATE TABLE IF NOT EXISTS retention_stats (
    entity_type TEXT NOT NULL,   -- 'actor' | 'studio'
    name TEXT NOT NULL,
    kept_count INTEGER NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (entity_type, name)
);
```
- `save_retention_stats(actor_counts: dict[str, int], studio_counts: dict[str, int])`: 트랜잭션 내 전체 갱신(replace).
- `get_retention_stats() -> dict[str, dict[str, int]]`: `{"actor": {...}, "studio": {...}}` 반환.

### 2. 스냅샷 갱신 (`src/meridian_x/report.py`)
- `retention_status()`가 이미 집계한 `actor_counts`, `studio_counts`를 `db.save_retention_stats()`로 저장. 추가 SSH 호출 없음.

### 3. 스코어링 공식 (`src/meridian_x/core.py`)
`score_taste(item: dict, config: dict, retention_stats: dict | None = None) -> tuple[float, list[str]]`
- **배우 매칭** (`classify.artists` + `artist_aliases`):
  - 등록 바닥 점수 `+30.0` + 잔존 보너스 `round(math.log2(1 + kept) * 10, 1)` (예: 0편→+30.0, 5편→+55.8, 25편→+77.0)
- **스튜디오 매칭** (`classify.studios` + aliases, `FC2` 패턴 포함):
  - 등록 바닥 점수 `+10.0` + 잔존 보너스 `round(math.log2(1 + kept) * 5, 1)` (예: 1편→+15.0, 20편→+32.0, 58편→+39.4)
- **미매칭 항목**: `0.0` (`reasons = []`)
- 배우와 스튜디오가 동시에 매칭되면 합산.

### 4. 수집 연동 (`src/meridian_x/collect.py`)
- `config.get("collection", {}).get("scoring", {})`:
  - `enabled` (bool, 기본 `True`)
  - `min_score` (float, 기본 `0.0` — `0`이면 차단 없이 정렬+로그만 수행)
- `_filter_and_send()`에서 `new_items`를 `score_taste()` 내림차순 안정 정렬(stable sort) 후 `min_score > 0`이면 미만 항목 스킵 로그 출력, 상위 `remaining`개 처리 시 점수·사유 로그 출력.

## Left to the Builder
- `score_taste`의 정규화 매칭은 `classify._normalize_name` 또는 공통 helper로 중복 없이 연결.
- `tests/test_core.py`, `tests/test_db.py`, `tests/test_collect.py`, `tests/test_report.py`에 단위 테스트 추가.

# CLI Usage Guide (운영 및 실행 가이드)

Meridian-X의 실제 운영 시나리오별 명령어 실행 가이드입니다.

---

## 1. 정기 자동화 및 원클릭 파이프라인

수집된 미디어를 정제하고 라이브러리에 안전하게 정돈하는 8단계 일괄 실행 파이프라인입니다.

```bash
# 변경 사항 사전 점검 (강력 권장)
uv run meridian pipeline --dry-run

# 파이프라인 전체 실행 (stop → filter → label → sync → tidy → classify → 갱신 → report)
uv run meridian pipeline

# Jellyfin 라이브러리 갱신을 생략할 경우
uv run meridian pipeline --no-refresh

# JPN/ 폴더 내 파일 웹 DB 조회 기반 배우 폴더 2차 재분류 활성화
uv run meridian pipeline --lookup-jav
```

---

## 2. 미디어 수집 (Ingestion)

### 정기 RSS 수집 (`transmission`)
```bash
# 전체 소스(OneJAV, Sukebei, XXXClub, TorrentGalaxy) RSS 수집
uv run meridian transmission

# 특정 소스만 선택 수집
uv run meridian transmission --source onejav
uv run meridian transmission --source sukebei
uv run meridian transmission --source tgx

# 수집 최대 개수 지정
uv run meridian transmission --max-downloads 50
```

### 키워드 검색 및 선별 수집 (`search`)
```bash
# 대화형 모드: 번호 선택식 수집 (1080p 및 WRB/XC 릴 우선 정렬)
uv run meridian search "Dakota Doll"

# Sukebei JAV 검색
uv run meridian search "MINAMO" --source sukebei

# TorrentGalaxy 서양 고화질 검색
uv run meridian search "Angela White" --source tgx

# 자동 전체 수집 (요청 간격 3초 delay로 차단 방지)
uv run meridian search "Dakota Doll" --auto --delay 3
```

---

## 3. 개별 운영 명령어

```bash
# 기존 토렌트 광고 파일 일괄 제외
uv run meridian filter

# 기존 토렌트 메이커/배우 labels 자동 설정
uv run meridian label

# Transmission labels → Jellyfin Tags 동기화
uv run meridian sync

# 원격 정리 (정크삭제 → Flatten → 파일명정리)
uv run meridian tidy

# 원격 분류 (SSH 하이브리드 분류)
uv run meridian classify --dry-run
uv run meridian classify

# 시스템 디스크 사용량 및 토렌트 상태 요약 리포트
uv run meridian report
```

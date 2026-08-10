# Meridian-X Roadmap

미디어 컬렉션 자동화 큐레이션 도구 (`RSS 수집` → `정제` → `메타데이터 조회` → `분류` → `Jellyfin 동기화`)

---

## 📌 Milestone Overview

| Version | Status | Milestone Highlights | Design Specs / Plans |
| :--- | :---: | :--- | :--- |
| **v0.1** | ✅ Done | Core Pipeline & Transmission RPC 전송 | `2026-06-08-transmission-rpc-integration` |
| **v0.2** | ✅ Done | Multi-Source (OneJAV / XXXClub) & SOPS/Age 암호화 | `2026-06-08-multi-source-architecture`<br>`2026-07-26-sops-age-encryption` |
| **v0.3** | ✅ Done | JAV 하이브리드 메타데이터 엔진 (FANZA + JavBus + OneJAV) & Jellyfin 태그 동기화 | `2026-08-09-jpn-classification-and-metadata` |
| **v0.4** | ✅ Done | West 미디어 StashDB GraphQL 연동 & 배우/스튜디오 분류 | `2026-08-09-stashdb-west-classification-and-metadata` |
| **v0.5** | ✅ Done | SQLite3 데이터베이스 (`meridian.db`) 통합 & 레거시 캐시 마이그레이션 | `2026-08-09-sqlite-metadata-store` |
| **v0.6** | 🛠️ Planned | Dry-Run 미리보기 강화 & 라이브러리 정리 최적화 | - |

---

## 🚀 Completed Milestones

### 1. Core Pipeline & Transmission RPC (v0.1)
- [x] **Transmission RPC 클라이언트**: `transmission-rpc` 기반 토렌트 추가, paused 제어, labels, file-unwanted 필터 통합 (`transmission.py`)
- [x] **원격 정리 및 분류 (SSH)**: `tidy` (정크 삭제, Flatten, 대소문자 중복 통합) & `classify` (하이브리드 SSH mv 분류)
- [x] **시스템 리포트**: 디스크 사용량 및 Transmission 토렌트 상태 조회 (`report.py`)

### 2. Multi-Source Architecture & Security (v0.2)
- [x] **Multi-Source 오케스트레이터**: `sources/` 모듈 분리 (`onejav.py`, `xxxclub.py`), CLI `--source` 플래그 지원
- [x] **Cloudflare 우회 (SSH Alias)**: 원격 SSH `lt` 커맨드 경유로 OneJAV 페이지 및 `.torrent` 바이너리 수집
- [x] **XXXClub Magnet 추출 및 필터**: Magnet 링크 직접 파싱 및 화이트리스트 셋 필터링
- [x] **SOPS + Age 설정 암호화**: `settings.json.sops` 암호화 추적 및 `core.load_config()` 자동 복호화 지원

### 3. JAV Multi-Tier Metadata Engine (v0.3)
- [x] **필드 단위 병합 Resolver (`jav_metadata.py`)**:
  - 1차: FANZA API (공식 타이틀, 배우, 메이커, 장르)
  - 2차: JavBus / Jav321 Web DB (SSH Lookup)
  - 3차: OneJAV SSH Lookup Fallback
- [x] **자동 폴더 분류 연동**: 품번 조회 결과에 따라 `Actors/{배우명}/` 1차 우선순위 이동, 미조회 시 스튜디오/장르/`JPN/` 이동
- [x] **Jellyfin Metadata & Tag Sync**: Jellyfin REST API를 경유하여 JAV 메타데이터(Studios, Genres, People, Tags) 자동 업데이트 (`jellyfin.py`)

### 4. West Media StashDB Metadata Engine (v0.4)
- [x] **StashDB GraphQL API Resolver (`west_metadata.py`)**:
  - 파일명 불필요 키워드/해상도/날짜 태그 정제 (`clean_search_term`)
  - StashDB `queryScenes` GraphQL API 메타데이터 (Performers, Studio, Tags, Title, Date) 수집
- [x] **West 분류 및 Jellyfin 동기화**: `Actors/{배우명}/` 및 `{스튜디오명}/` 라우팅, Jellyfin Performers/Studio/Tags 동기화

### 5. SQLite3 Infrastructure & Cache Integration (v0.5)
- [x] **SQLite3 저장소 (`meridian.db`)**: `MeridianDB` DAO 구축, WAL 모드 적용 (`PRAGMA journal_mode=WAL;`), 원자적 트랜잭션 보장
- [x] **통합 스키마 구축**:
  - `download_history` (수집 이력 및 소스별 prefix 관리)
  - `jav_metadata` (JAV 메타데이터 원본 및 파싱 필드 DB 저장)
  - `west_metadata` (West StashDB 메타데이터 DB 저장)
- [x] **레거시 이관 및 `.bak` 자동 백업**: 기존 `downloaded_history.txt`, `logs/*_cache.json` 읽은 후 `.bak` 백업 전환으로 파일 I/O 오버헤드 완벽 제거

---

## 🔮 Future Roadmap (v0.6+)

### 🎯 Short-Term (다음 단계)
- [ ] **Dry-Run 미리보기 강화**: `filter`, `label`, `classify` 실행 전 영향받는 파일 목록 및 분류 예정 디렉토리 상술 표시
- [ ] **미사용 의존성 정리**: `pyproject.toml` 내 사용 중단된 `playwright` 의존성 완전 제거
- [ ] **Stalled 토렌트 정리 자동화**: 미완료 + N일 경과 + 송신 피어 0 (`peersSendingToUs`) 토렌트 탐지/삭제 서브커맨드 추가. `--dry-run` 기본, 삭제 시 데이터 포함 여부 옵션 (`peersSendingToUs == 0` and `addedDate > N days` 기준)

### 🌐 Long-Term (향후 확장)
- [ ] **Cloudflare D1 클라우드 동기화**: 다중 머신/클라우드 환경 대비 `meridian.db` ➔ Cloudflare D1 백업 모듈
- [ ] **Gradio 기반 Web Dashboard**: Gradio를 활용하여 수집 이력 조회, 미디어 분류 상태 모니터링, 토렌트 상태 및 메타데이터 수동 재조회 웹 UI 구축 (`uv run meridian dashboard`)

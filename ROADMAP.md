# Meridian-X Roadmap

## Current

- **v0.2** — Multi-Source 수집 및 SQLite3 메타데이터/히스토리 저장소 구축
  - Multi-Source 수집: OneJAV (SSH Cloudflare 우회), XXXClub (RSS magnet)
  - SQLite3 저장소: `meridian.db` (다운로드 히스토리, JAV 메타데이터, West StashDB 메타데이터 캐시 통합)
  - `transmission` 명령어: RSS → paused → filter → labels → start
  - `filter` 명령어: 기존 토렌트 광고 파일 일괄 제외
  - `label` 명령어: 메이커 코드(JAV) / 스튜디오+배우(West) 자동 설정
  - `classify` 명령어: 원격 미디어 파일 분류 (FANZA / JavBus / OneJAV / StashDB 연동)
  - `tidy` 명령어: 원격 파일 정리 및 Flatten

## Completed

### Multi-Source Architecture (Codex Option 1: Source Functions)

- 설계 문서: `docs/superpowers/specs/2026-06-08-multi-source-architecture-design.md`
- [x] `sources/` 패키지 생성: `discover()` + `resolve()` 함수 per source
- [x] `sources/onejav.py`: OneJAV 수집 이관 (RSS → page → .torrent bytes)
- [x] `sources/xxxclub.py`: XXXClub RSS → magnet link 직접 추출
- [x] `transmission.py`: `add_magnet()` 추가
- [x] `collect.py`: 오케스트레이터로 재작성 (source 루프)
- [x] `settings.json`: `sources` 딕셔너리 구조로 변경
- [x] CLI: `--source` 플래그 (`all` / `onejav` / `xxxclub`)
- [x] History: source prefix ID (`onejav:SNOS155`, `xxxclub:...`)

### Storage & Cache Optimization

- 설계 문서: `docs/superpowers/specs/2026-08-09-sqlite-metadata-store-design.md`
- [x] **SQLite3 데이터베이스 통합**: `download_history`, JAV 메타데이터, West 메타데이터 캐시를 단일 `meridian.db`로 마이그레이션 및 WAL 모드 도입
- [x] **레거시 이관 및 `.bak` 자동 백업**: 기존 `.txt` / `.json` 파일 자동 이관 후 `.bak` 백업 전환

## Next / Future Improvements

- [ ] **dry-run label/filter 미리보기**: 변경 전 어떤 label/filter 적용되는지 상세 대상 항목 표시
- [ ] **Cloudflare D1 클라우드 동기화 옵션**: 다중 머신 환경 대비 `meridian.db` → Cloudflare D1 동기화 선택 모듈

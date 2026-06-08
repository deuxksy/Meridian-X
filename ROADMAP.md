# Meridian-X Roadmap

## Current

- **v0.1** — OneJAV RSS 수집 → Proxmox Transmission RPC 전송
  - `transmission` 명령어: RSS → paused → filter → labels → start
  - `filter` 명령어: 기존 토렌트 광고 파일 일괄 제외
  - `label` 명령어: 메이커 코드(JAV) / 스튜디오+배우(West) 자동 설정
  - `classify` 명령어: 미디어 파일 분류 (FANZA 메타데이터)
  - 단일 Source: OneJAV

## Next

### Multi-Source Architecture (Codex Option 1: Source Functions)

- 설계 문서: `docs/superpowers/specs/2026-06-08-multi-source-architecture-design.md`
- 검증: Codex gpt-5.5 + Gemini gemini-3.1-pro-preview 교차 검증 완료
- [ ] `sources/` 패키지 생성: discover() + resolve() 함수 per source
- [ ] `sources/onejav.py`: 기존 collect.py 로직 이관 (RSS → page → .torrent bytes)
- [ ] `sources/xxxclub.py`: RSS → magnet link 직접 추출 (CF 우회 옵션)
- [ ] `transmission.py`: add_magnet() 추가 (filename 방식)
- [ ] `collect.py`: 오케스트레이터로 재작성 (source 루프)
- [ ] `settings.json`: `sources` 딕셔너리 구조로 변경
- [ ] CLI: `--source` 플래그 (all / onejav / xxxclub)
- [ ] History: source prefix ID (`onejav:SNOS155`, `xxxclub:...`)

### Improvements

- [ ] **FANZA 연동**: JAV 토렌트에 배우 이름 label
- [ ] **dry-run label/filter 미리보기**: 변경 전 어떤 label/filter 적용되는지 표시

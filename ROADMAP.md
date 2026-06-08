# Meridian-X Roadmap

## Current

- **v0.1** — OneJAV RSS 수집 → Proxmox Transmission RPC 전송
  - `transmission` 명령어: RSS → paused → filter → labels → start
  - `filter` 명령어: 기존 토렌트 광고 파일 일괄 제외
  - `label` 명령어: 메이커 코드(JAV) / 스튜디오+배우(West) 자동 설정
  - `classify` 명령어: 미디어 파일 분류 (FANZA 메타데이터)
  - 단일 Source: OneJAV

## Next

### Source 확장

- [ ] **xxxclub.to** West RSS 수집 추가
  - RSS 파싱 (xxxclub.to 피드 형식)
  - 파일 추출 로직 (torrent magnet/direct link)
  - Transmission RPC 전송 (기존 add_torrent 재사용)
  - 설정에 multi-source 구조
  - **Cloudflare 우회**: xxxclub.to는 CF 보호가 걸릴 수 있음
    - 대응: cookie/token 유지, `cloudscraper`, fallback 처리
  ```json
  "sources": {
    "onejav": { "rss_url": "...", "type": "jav" },
    "xxxclub": { "rss_url": "...", "type": "west" }
  }
  ```

### Improvements

- [ ] **FANZA 연동**: JAV 토렌트에 배우 이름 label (메이커 코드 → FANZA API → 배우)
- [ ] **CLI source 선택**: `meridian transmission --source xxxclub`
- [ ] **dry-run label/filter 미리보기**: 변경 전 어떤 label/filter 적용되는지 표시
- [ ] **history per source**: 현재 단일 파일 → source별 분리

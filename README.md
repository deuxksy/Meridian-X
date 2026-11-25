# Meridian-X

[![Security Scan](https://github.com/deuxksy/Meridian-X/actions/workflows/security-scan.yml/badge.svg)](https://github.com/deuxksy/Meridian-X/actions/workflows/security-scan.yml)

*품격 있는 디지털 수집가를 위한 우아한 솔루션*

**Meridian-X**는 프라이빗 미디어 컬렉션을 자동 수집·정리·분류·동기화하는 Python 자동화 스위트입니다. 고화질(FHD/4K) 멀티소스 수집과 실제 디스크 잔존율 기반 취향 스코어링, 광고 정크 정리, 메타데이터 조회, Jellyfin 태그 동기화 및 SSH 원격 분류를 하나의 운영 흐름으로 제공합니다.

---

## 🧐 철학 (Philosophy)

신사의 서재는 언제나 정갈해야 합니다. **Meridian-X**는 보이지 않는 곳에서 다음과 같이 봉사합니다:
- **수집 (Collect):** Whisparr가 수집할 수 없는 특별한 작품들을 신사의 취향에 맞추어 우아하게 수집합니다.
- **정화 (Sanitize):** 파일명에 붙은 보기 흉한 광고 문구, 홍보용 태그, 그리고 가치 없는 부산물들을 정중하게 제거합니다.
- **큐레이션 (Curate):** 동양과 서양, 그리고 특별한 취향에 맞춰 콘텐츠를 자동으로 분류하고 적절한 위치로 안내합니다.

---

## 🔄 워크플로우 (Workflow)

수집(Ingestion) → 8단계 큐레이션 파이프라인 → 분류 우선순위 전체 흐름 다이어그램은 [아키텍처 & 워크플로우](./docs/okf/explanation/architecture-and-workflow.md) 참조.

---

## 📁 프로젝트 구조

```text
Meridian-X/
├── README.md
├── AGENTS.md
├── pyproject.toml
├── uv.lock
├── config/
│   ├── settings.json          # 전체 설정 (git 제외)
│   ├── settings.json.sops     # sops+age 암호화 추적본
│   └── settings.json.example  # 설정 템플릿
├── docs/                      # OKF Diátaxis 문서 및 아카이브
│   ├── okf/                   # 공식 지식 프레임워크 (Tutorials, How-To, Reference, Explanation)
│   ├── archive/               # 비관리형 과거 기획 및 외부 참조 자료
│   └── superpowers/           # AI 에이전트 설계/계획서
├── tests/                     # pytest 회귀 테스트 스위트 (21개 모듈)
└── src/meridian_x/
    ├── cli.py                 # CLI 진입점
    ├── collect.py             # Multi-source 수집 오케스트레이터
    ├── sources/               # 수집 소스 (onejav, sukebei, xxxclub, torrentgalaxy)
    ├── transmission.py        # Transmission RPC 클라이언트
    ├── jellyfin.py            # Jellyfin REST API 클라이언트
    ├── tidy.py                # 원격 파일 정리 (SSH)
    ├── classify.py            # 원격 파일 분류 (SSH)
    ├── report.py              # disk/잔존율(retention)/토렌트 상태 리포트
    ├── db.py                  # SQLite 저장소 (download_history, jav_metadata, west_metadata, actresses, retention_stats)
    ├── jav_lookup.py          # JAV Web DB (Jav321/JavBus) 및 OneJAV 조회
    ├── jav_metadata.py        # 메타데이터 통합 Resolver
    ├── west_metadata.py       # StashDB GraphQL API West 메타데이터 Resolver
    ├── remote.py              # SSH 원격 명령, 원격 curl, 프록시 fetch 헬퍼 모듈
    └── core.py                # 공통 함수 (설정/화질필터/중복선별/취향스코어링)
```

---

## 🚀 빠른 시작 (Quick Start)

```bash
# 1. 의존성 설치 및 설정 복원
uv sync
cp config/settings.json.example config/settings.json
# 또는 sops로 복원: sops --decrypt --input-type binary --output-type binary config/settings.json.sops > config/settings.json

# 2. 미디어 수집 (정기 RSS 수집 및 키워드 검색)
uv run meridian transmission                      # 4대 소스 정기 수집
uv run meridian favorite                          # 즐겨찾기(token URL) 수동 수집
uv run meridian search "Dakota Doll"               # 대화형 키워드 검색 및 선별 수집

# 3. 8단계 큐레이션 파이프라인 일괄 실행
uv run meridian pipeline --dry-run                # 변경 사항 미리보기 (권장)
uv run meridian pipeline                          # stop→filter→label→sync→tidy→classify→갱신→report
```

---

## 📚 공식 문서 (OKF Documents)

모든 상세 가이드와 기술 명세는 [Diátaxis](https://diataxis.fr/) 프레임워크 기반 **[OKF Documentation Hub](./docs/okf/README.md)**에 체계적으로 수록되어 있습니다:

| 분류 (Diátaxis) | 문서 허브 | 설명 |
| :--- | :--- | :--- |
| **Docs Hub** | [Documentation Hub](./docs/README.md) | `docs/` 전체 구조 안내 (OKF, archive, superpowers) |
| **Reference (OKF Hub)** | [OKF Documentation Hub](./docs/okf/README.md) | 개별 OKF 문서 전체 목록의 단일 기준본(SSoT) 허브 |
| **Tutorials** | [Tutorials Hub](./docs/okf/tutorials/README.md) | 설치, 초기 설정 복원 및 첫 Dry-run 실습 안내 |
| **How-To** | [How-To Guides Hub](./docs/okf/how-to/README.md) | CLI 운영, SOPS 설정 초기화·재암호화, 보안 스캔 구축 절차 |
| **Reference** | [Reference Hub](./docs/okf/reference/README.md) | `settings.json` 키 스키마 및 서브커맨드 전체 옵션 명세 |
| **Explanation** | [Explanation Hub](./docs/okf/explanation/README.md) | 2단계 아키텍처, 취향 스코어링 원리, 보안 스캔 설계 및 로드맵 |
| **Archive** | [Docs Archive](./docs/archive/README.md) | 비관리형 과거 기획 및 외부 참조 자료 |

---

## 📄 라이선스 (License)

MIT License — [LICENSE](./LICENSE) 참조.

---

*"질서는 정신의 건전함이자, 신체의 건강이며, 도시의 평화이다."*

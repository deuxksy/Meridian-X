# CLI Options Reference (명령어 및 옵션 명세)

Meridian-X의 모든 서브커맨드와 지원 옵션에 대한 상세 명세서입니다.

---

## 1. 서브커맨드 요약

| 서브커맨드 | 설명 | 주요 플래그 |
| :--- | :--- | :--- |
| `pipeline` | 8단계 큐레이션 파이프라인 일괄 실행 | `--dry-run`, `--no-refresh`, `--lookup-jav` |
| `transmission` | 4대 소스 RSS 정기 수집 및 Transmission RPC 큐잉 | `--dry-run`, `--source`, `--max-downloads` |
| `search` | 키워드 검색 및 선별/자동 다운로드 | `--category`, `--source`, `--auto`, `--delay`, `--dry-run` |
| `filter` | 기존 토렌트 광고/정크 파일 일괄 제외 | `--dry-run` |
| `label` | 기존 토렌트 메이커 코드/배우 라벨 자동 설정 | `--dry-run` |
| `sync` | Transmission 라벨 ➔ Jellyfin 태그 동기화 | - |
| `tidy` | SSH 원격 정크 삭제, 폴더 Flatten, 파일명 정리 | `--dry-run` |
| `classify` | SSH 원격 파일 분류 (하이브리드 메타데이터 조회) | `--dry-run`, `--no-lookup`, `--lookup-jav` |
| `report` | 스토리지 용량 및 Transmission 토렌트 상태 리포트 | - |

---

## 2. 상세 옵션 명세

### `pipeline`
```bash
uv run meridian pipeline [OPTIONS]
```
| 옵션 | 설명 | 기본값 |
| :--- | :--- | :--- |
| `--dry-run` | 실제 파일 이동이나 API 변경 없이 결과만 출력 | `False` |
| `--no-refresh` | 파이프라인 완료 후 Jellyfin 라이브러리 갱신 스킵 | `False` |
| `--lookup-jav` | `JPN/` 폴더 내 파일 웹 DB 조회 기반 배우 폴더 2차 분류 활성화 | `False` |

### `transmission`
```bash
uv run meridian transmission [OPTIONS]
```
| 옵션 | 설명 | 기본값 |
| :--- | :--- | :--- |
| `--dry-run` | 실제 전송 없이 수집 대상 항목만 출력 | `False` |
| `--source NAME` | 수집 소스 지정 (`onejav`, `sukebei`, `xxxclub`, `torrentgalaxy`/`tgx`) | `None` (전체 소스) |
| `--max-downloads N` | 최대 다운로드 수 (전체 소스 합산) | `30` |

### `search`
```bash
uv run meridian search <QUERY> [OPTIONS]
```
| 옵션 | 설명 | 기본값 |
| :--- | :--- | :--- |
| `--source NAME` | 검색 대상 소스 (`xxxclub`, `sukebei`, `torrentgalaxy`/`tgx`) | `xxxclub` |
| `--category CAT` | 검색 대상 카테고리 (Sukebei: `2_2`, XXXClub: `1080p`, TGx: `42`) | 소스별 기본값 |
| `--auto` | 자동 전체 다운로드 모드 (비대화형) | `False` (대화형 선택) |
| `--delay SEC` | 자동 모드 요청 간격 delay (초) | `5.0` |
| `--dry-run` | 실제 다운로드 추가 없이 결과만 확인 | `False` |

### `classify`
```bash
uv run meridian classify [OPTIONS]
```
| 옵션 | 설명 | 기본값 |
| :--- | :--- | :--- |
| `--dry-run` | 실제 파일 이동 없이 분류 결과 미리보기 | `False` |
| `--no-lookup` | 외부 API 메타데이터 조회 스킵 (단순 파일명 규칙 매칭만 수행) | `False` |
| `--lookup-jav` | `JPN/` 폴더 내 파일 웹 DB 조회 기반 배우 폴더 2차 분류 활성화 | `False` |

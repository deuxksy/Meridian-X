# Meridian-X Documentation Hub

Meridian-X 프로젝트의 사람용 문서 허브입니다. 문서는 Diátaxis 프레임워크 4분면(Tutorials, How-To, Reference, Explanation)에 따라 분리합니다.

---

## 📚 Diátaxis 문서 분류 (Diátaxis Index)

### 1. 🚀 Tutorials (튜토리얼)
- [Tutorials Hub](./tutorials/README.md): 입문 및 첫 실행 가이드
- [Quick Start Guide](../README.md#-사용법-usage): 설치, 설정 및 파이프라인 첫 실행 가이드

### 2. 💡 How-To Guides (사용법 가이드)
- [How-To Hub](./how-to/README.md): 특정 운영 작업 수행 절차
- [CLI 사용 설명서](../README.md#-주요-기능-features): `collect`, `search`, `filter`, `label`, `sync`, `tidy`, `classify`, `pipeline`, `report` 개별 명령어 가이드
- [Security Scan 구현](./how-to/security-scan-implementation.md): 보안 스캔 CI/CD 파이프라인 구축 계획

### 3. 📖 Reference (참조)
- [Reference Hub](./reference/README.md): 설정, CLI, 문서 구조 참조
- [Configuration Spec](../README.md#-설정-configuration): `config/settings.json` 및 `sops` 암호화 설정 명세
- [CLI Options Reference](../README.md#-명령어-옵션): 명령줄 옵션 모음

### 4. 🧠 Explanation (설명 및 설계)
- [Explanation Hub](./explanation/README.md): 아키텍처, 설계 결정, 배경 설명
- [Project Roadmap](../ROADMAP.md): 버전별 현황 및 향후 로드맵
- [Security Scan 설계](./explanation/security-scan-design.md): 보안 스캔 도입 배경 및 설계 결정

---

## 📁 디렉터리 안내 (Subdirectories)

- **`docs/tutorials/`**: 입문 및 첫 실행 중심 문서
- **`docs/how-to/`**: 특정 운영 작업 수행 절차
- **`docs/reference/`**: 설정, CLI, 문서 구조 참조
- **`docs/explanation/`**: 아키텍처, 설계 결정, 배경 설명
- **`docs/archive/`**: 외부 산출물, 과거 설계 자료, API 스냅샷 보관용 디렉터리. 일반 문서 인덱스에서는 제외
- **`docs/superpowers/`**: AI 에이전트 설계 사양(`specs/`) 및 실행 계획(`plans/`) (내부 관리용)

# GitHub Actions Security Scan 설계

## 개요

`meridian-x` Python 프로젝트 종합 보안 스캔 자동화 시스템입니다.
- **의존성 취약점 검사**: pip-audit
- **정적 분석**: Bandit
- **Secret 스캔**: Gitleaks,- **파일 시스템 스캔**: Trivy

## 목표
- 모든 PR에서 자동화된 보안 검사 수행
- 심각한 취약점 조기에 발견하여 보안 강화
- GitHub Security 탭에서 통합된 보안 대시보드 제공

- 보안팀에 Slack 알림을 통한 빠른 대응 가능

- 분석 결과를 SAR 형식으로 GitHub Security 탭에 업로드

- 보안 스캔 결과를 리포트 생성

- 자동화된 보안 감사

- 취약점 이력 및 추세 파악 용이

- 심각한 취약점 발견 시 즉각 PR 실패
  - 보안팀 검토 및 대응 속도 향상
- 취약점 발견 시 Slack 알림을 통한 빠른 알림 제공
  - 경고만 표시하고 PR 생성
  - 분석 결과를 GitHub Security 탭에서 종합 관리 가능

- 보안 강화를 점진적으로 진행
- 비용 효소
- 보안 부채 최소화
- 자동화된 검사로 빠른 피드백 가능
- SAR 업로드를 통한 통합된 보안 관리 제공
- 온프레미션이 쉽기 쉽 프로세스로 관리 가능
- 취약점 발견 시 즉각적인 알림 전송 방지
  - 취약점 데이터 GitHub Security 탭에서 영구 보관
- 분석 결과를 SAR 형식으로 표준화하여 GitHub Security 탭에서 쉽게 확인 가능

## 설계 원칙
- **KISS**: 각 도구는 단순하고 효과적으로 사용
- **YAGNI**: 현재 필요한 기능만 구현
- **DRY**: 워크플로 구성을 재사용하여 다른 프로젝트에 적용 가능

## 스캔 범위

### 1. 의존성 취약점 ( pip-audit )
- **목적**: `requirements.txt`, `pyproject.tom`에 정의된 의존성 패키의 알려진 CVE 취약점 검사
- **이유**: 의존성 취약점은 공급망 공격 벡터로 가장 흔한 진입점
- **실행**: 매일 자동화된 스캔 또는 PR 생성 시

- **대안**: safety (유료), Dependabot (오픈 전용)

- **선택 이유**: pip-audit은 PyPA 권장 도구이고, pipenv/uv 환경 모두 지원하며, GitHub Actions와 쉽게 통합됨

### 2. 정적 분석( Bandit )
- **목적**: Python 코드에서 보안 취약점(하드코딩, 시크릭 등) 정적 분석
- **검사 범위**:
  - 하드코딩된 비밀번호 하드코딩
  - 약한 암호화 알고리즘 사용
  - SQL Injection, Command Injection 등
- **이유**: 코드 작성 시 보안 모범을 사전에 검사하면 배포 후 발견하기 어렵기 때문
- **실행**: 심각도 이슈가 PR 실패 (`--severity-threshold medium`)
- **대안**: Semgrep (SaaS, 유료), Ruff (오픈 전용), - 더 강력하지 설정 복잡
- **선택 이유**: Bandit은 가볍고 Python 특화 도구이며, GitHub Actions와 기본 통합됨

### 3. Secret 스캔( Gitleaks )
- **목적**: Git 리포지토리에 커밋된 비밀정보(credential, API key 등) 탐지
- **검사 범위**:
  - `.env` 파일
  - 하드코딩된 비밀번호
  - API 키, 토큰
  - `.pem` 파일, 인증서
  - Private key 파일
- **이유**: Secret 노출은 즉시 보안 사고로 가장 치명적입니다.
  - **실행**: Secret 발견 시 즉시 워크플로우 실패
- **대안**: Trivy Secret Scanning (무검)

- **선택 이유**: Gitleaks은 Git 리포지토리 특화된 도구이며, Git 리포지토리 스캔에 가장 적합합니다.

### 4. 파일 시스템 스캔( Trivy )
- **목적**: 프로젝트 파일 시스템 내의 설정 파일, 민감 정보 탐지
- **검사 범위**:
  - `.env`, `settings.json` 등의 설정 파일
  - 하드코딩된 비밀번호
  - 인증서, 키 파일
  - 로그 파일에 민감 정보
- **이유**: 파일 시스템 스캔은 애플리케이션 전체 보안 태세를 파악 가능
- **실행**: 취약점 발견 시 SAR 업로드만 하고 PR 생성
- **대안**: Snyk (오픰 전용), - 더 빠르고 설정 간단
- **선택 이유**: Trivy는 오픈 소스로 널리 사용되며, 컨테이너 스캔뿩 다양한 스캔 타입을 지원합니다.
  - 로컬 파일 시스템 스캔 기능을 제공합니다 (단일 도구로 집중 가능)
  - GitHub Actions와 통합 용이 높음

  - SAR 업로드 지원

  - PR 생성 시 SAR 업로드 단계에서 실패하지 않음

  - GitHub Security 탭 통합을 위한 단계별 접근 방식 채택

## 워크플로우 구조

```mermaid
flowchart TD
    A[Start] --> B[Setup Python]
    B --> C[pip-audit]
    B --> D[Bandit]
    B --> E[Gitleaks]
    B --> F[Trivy]
    F --> G{Aggregate Results}
    G --> H{Create SAR Ball]
    H --> I[Upload SAR]
    I --> J{PR Comment?]
    J --> K{Slack Alert?}
    K --> L{Fail if Critical?}

    L --> M[End]

    style start stroke-dasharray
    0,1
    0,1,0,1,1

    start[0,1,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1
```
## 워크플로우 실행

```yaml
name: Security Scan
on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: '0 9 * * 1'  # 매일 오전 9시 (KST)
  workflow_dispatch:

    - push:
    branches: [main]
  workflow_call:

  workflow_dispatch:

jobs:
  scan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
      security-events: write

    steps:
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install dependencies
        run: |
          pip install -r requirements pip-audit bandit
      - name: Dependency Vulnerability Scan
        run: pip-audit -r requirements --ignore-vulns --skip-editable . --progress-handler=pip_audit._cli.cli:displayProgressBar(progressHandler, output_handler)
      - name: Static Analysis (Bandit)
        run: bandit -r src -ll -ii
      - name: Secret Scan (Gitleaks)
        uses: gitleaks/gitleaks-action@v2
        with:
          args: --verbose --repo-path=.
      - name: Filesystem Scan (Trivy)
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          ignore-unfixed: true
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'HIGH,          exit-code: 1
      - name: Aggregate Results
        run: |
          echo "## Security Scan Summary"
          echo "| Tool | Status |"
          echo "|------|-------|------------|"
          # pip-audit results
          if [ -f "results/pip-audit.txt" ]; then
            echo "pip-audit: PASSED"
          else
            echo "pip-audit: FAILED"
            cat "Results/pip-audit.txt"
            exit 1
          fi
          # Bandit Results
          if [ -f "Results/bandit.txt" ]; then
            echo "Bandit: PASSED"
          else
            echo "Bandit: FAILED"
            cat "Results/bandit.txt"
            exit 1
          fi
          # Gitleaks Results
          if [ -f "Results/gitleaks.txt" ]; then
            echo "Gitleaks: PASSED"
          else
            echo "Gitleaks: FAILED"
            cat "Results/gitleaks.txt"
            exit 1
          fi
          # Trivy Results
          if [ -f "Results/trivy-results.sarif" ]; then
            echo "Trivy: PASSED"
          else
            echo "Trivy: FAILED"
            cat "Results/trivy-results.sarif"
            exit 1
          fi
      - name: Create SAR Ball
        run: |
          # Combine all SAR results
          jq -s 'select(.[].output' != null' | select(.report.results != null and select(.report.tool == "pip-audit") and new_text += "\nDependency: " + .report.findings[].join("\n")
            } else if .report.tool == "bandit") and new_text += "\nBandit: " +.report.findings[].join("\n")
            } else if .report.tool == "gitleaks") and new_text += "\nGitleaks: "+ .report.findings[].join("\n")
            } else if .report.tool == "trivy") and new_text += "\nTrivy: "+ .report.findings[].join("\n")
            }
          fi
          echo "" > results.sarif.json
      - name: Upload SAR
        uses: actions/upload-artifact@v4
        with:
          name: SAR_BALL_RESULTS
          path: results.sarif.json
          retention-days: 30
      - name: PR Comment
        uses: actions/github-script@v7
        if: failure()
        with:
          script: |
            const fs = require('fs');
            const results = JSON.parse(fs.readFileSync('results.sarif.json', 'r'));
            const vulnerabilities = results.runs?.flatMap(r => r.run);
              const { tool, report} = r);
            const finding = report.findings.find(f => f.severity === 'HIGH' || f.severity === 'CRITICAL');
            if (finding) {
              core.setFailed(`Security vulnerability found in ${finding.tool}`);
              core.setOutput(`::error ::${finding.message}`);
            } else if (finding.severity === 'MEDIUM') {
              core.warning(`::warning :: ${finding.message}`);
            }
          });
          // Add comment to PR
          const output = `## ⚠ Security Vulnerability Found\n\n**Tool:** ${finding.tool}\\n**Severity:** ${finding.severity}\n**Message:** ${finding.message}\n\nPlease review the [Security tab](${process.env.GITHUB_SERVER_URL}/${process.env.GITHUB_REPOSITORY}/actions/runs/${process.env.GITHUB_RUN_ID}) for details.`;
            core.setFailed('Security vulnerabilities found');
          }
      - name: Slack Alert
        if: failure()
        run: |
          curl -X POST -H 'Content-type: application/json' \
            -d '{
              "text": "🚨 Security vulnerabilities found in ${{ github.repository }}\nPlease review: security scan results in the GitHub Actions tab."}' \
            ${{ secrets.SLACK_WEBHOOK_URL }}
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
          SLACK_CHANNEL_ID: ${{ secrets.SLACK_CHANNEL_ID }}
      - name: Fail on Critical
        if: failure() && steps.*report.results.some(r.run['CRITICAL'])
        run: exit 1
```

## 실행 시점

### 자동 실행
- **PR 생성/업데이 시**: main 브랜치에 push 시 실행
- **PR에서**: 수동 실행 또는 월요일 오전 9시 (KST) 실행
- **매일 스캔**: 매일 특정 시간에 실행 (자동화된 모니터링)

- **수동 실행**: `workflow_dispatch` 이벤트 통해 언제든 실행 가능
## PR 정책

### Critical 취약점
- **Secret 노출**: PR 실패
- **Critical/High 취약점**: PR 실패
- **Medium/Low 취약점**: 경고만 표시하고 PR 생성
### 알림 정책
- **Critical/High 취약점**: Slack 알림 발송
- **Medium/Low 취약점**: PR 코멘트에만 로그 표시
## 비용
- **pip-audit**: 무료
- **Bandit**: 무료
- **Gitleaks Action**: 무료
- **Trivy**: 오픈 소스
- **Slack**: Slack Webhook URL 및 Channel ID 필요 (Secret으로 설정)
- **GitHub Actions**: 표준 실행 시간 (약 2분)
- **저장**: 30일 (SAR)
- **취약점 데이터**: GitHub Security 탭에서 영구 보관
## 제약사항
### Secret 설정
- `SLACK_WEBHOOK_URL`: Slack Webhook URL (필수,- Slack 알림용)
- `SLACK_CHANNEL_ID`: Slack Channel ID (필수,- Slack 알림용)
### 브랜치 보호
- `main` 브랜치만 보호
- PR은 `main`에서만 생성 가능

## 참고 자료
- [GitHub Actions Security Scans](https://docs.github.com/en/code-security/supply-chain-security)
- [pip-audit Documentation](https://pypi.org/project/pip-audit/)
- [Bandit Documentation](https://bandit.readthedocs.io/)
- [Gitleaks Documentation](https://github.com/gitleaks/gitleaks)
- [Trivy Documentation](https://aquasecurity.github.io/trivy/)
- [GitHub Actions SARIF Support](https://docs.github.com/en/code-security/sarif-support-for-code-scanning)

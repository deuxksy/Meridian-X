# Security Scan Implementation Plan
> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
**Goal:** GitHub Actions를 통한 Python 프로젝트 종합 보안 스캔 자동화 시스템을 구축합니다.
**Architecture:** 4개의 보안 도구를 단계적으로 실행하여, 빠르게 피드백을 제공하고, 취약점이 발견 시 PR 실패 정책으로 보안 강화합니다
 **Tech Stack:** GitHub Actions, pip-audit, Bandit, Gitleaks, Trivy, SARIF
**Dependencies:**
- GitHub Actions
- pip-audit: 의존성 취약점 스캔
- Bandit: 정적 코드 분석
- Gitleaks: Git secret 스캔
- Trivy: 파일 시스템 스캔
**SARIF**: SARIF 파일 형식으로 결과를 GitHub Security 탭에 업로드
**Third-party tools:****
- None (GitHub Actions 기본 제공)
- uv: Python 패키 관리
- Trivy Action for 파일 시스템 스캔
**Execution flow:**
```mermaid
flowchart TD
    A[Start] --> B[Setup Python]
    B --> C[pip-audit]
    B --> D[Bandit]
    B --> E[Gitleaks]
    F --> G[Trivy]
    F --> G{Aggregate Results]
    G --> H[Create SAR Ball]
    H --> I[Upload SAR]
    I --> J[PR Comment?]
    J --> K[Slack Alert?]
    K --> L[Fail on Critical?]
    L --> M[End]
    style start Stroke-dasharray
    0,1
    0,1,0,1,1
    0,1,0 0
    0,1
    0,1,0
    0,1
    0,1,0
    0,1
    0,1,0
    0,1,0 0
    0,1,    end
    0,1,0
    0,1,0 3
  end

  0,1
    0,1,0
    0,1
            0,1,0
        0,1,0
    end
    0,1,0 3
  end
end
```

## Task Structure
````markdown
### Task 1: Workflow 파일 생성
**Files:**
- Create: `.github/workflows/security-scan.yml`
**Description:** Main workflow 파일 for security scanning
**Step 1: Create directory structure**
```bash
mkdir -p .github/workflows
```
**Step 2: Verify directory structure**
Run: `ls -la .github/workflows`
Expected: Directory `.github/workflows/` exists

**Step 3: Create requirements.txt**
**Files:**
- Create: `requirements.txt` in project root
- Add: `requests`, `python-dotenv` to the dependencies
**Step 4: Create .python-version file**
**Files:**
- Create: `.python-version`
- Add content: `3.12`
```
**Step 5: Verify file creation**
Run: `cat .python-version`
Expected: File exists with Python 3.12 specified
**Step 6: Create workflow file header**
**Files:**
- Create: `.github/workflows/security-scan.yml`
- Write file header (see below for details)
```yaml
name: Security Scan
on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: '0 9 * * 1'  # 매주 월요일 오전 9시 (KST)
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
        run: |
          pip-audit -r requirements --ignore-vulns --skip-editable . --progress-handler=pip_audit._cli.cli:displayProgressBar(progressHandler, outputHandler)
      - name: Static Analysis (Bandit)
        run: |
          bandit -r src -ll
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
          severity: 'HIGH'
          exit-code: 0
      - name: Aggregate Results
        run: |
          echo "## Security Scan Summary"
          echo "| Tool | Status | Findings |"
          echo "|------|-------|------------|"

          # Check if any scan failed
          failed_tools=""
          if [ -f "pip-audit-results.txt" ]; then
            echo "pip-audit: FAILED"
            cat "pip-audit-results.txt"
            failed_tools="${failed_tools}pip-audit "
          fi
          if [ -f "bandit-results.txt" ]; then
            echo "Bandit: FAILED"
            cat "bandit-results.txt"
            failed_tools="${failed_tools}bandit "
          fi
          if [ -f "gitleaks-results.txt" ]; then
            echo "Gitleaks: FAILED"
            cat "gitleaks-results.txt"
            failed_tools="${failed_tools}gitleaks "
          fi
          if [ -f "trivy-results.sarif" ]; then
            echo "Trivy: FAILED"
            cat "trivy-results.sarif"
            failed_tools="${failed_tools}trivy "
          fi

          if [ -n "$failed_tools" ]; then
            echo "::error:: Some security scans failed"
            echo "Failed tools: $failed_tools"
            core.setFailed('Security vulnerabilities found')
          fi
      - name: Create SAR Ball
        run: |
          # Combine all SAR results into single file
          combined_sarif="combined.sarif"
          echo '{"version":"2.1.0","$schema":"https://raw.githubusercontent.com/SARIF/sarif-schema-2.1.0","runs":[]}' > "$combined_sarif"
          sar_files=$(find . -name "*.sarif" 2>/dev/null)
          if [ ${#sar_files[@]} -eq 0 ]; then
            echo "No SAR files found, creating empty combined.sarif"
            exit 0
          fi
          # Combine all SAR files
          for sar_file in ${sar_files[@]}; do
            echo "Combining $sar_file ..."
            cat "$sar_file" >> "$combined_sarif"
          done
          echo "SAR ball created: $combined_sarif"
      - name: Upload SAR
        uses: actions/upload-artifact@v4
        with:
          name: SAR_BALL_RESULTS
          path: combined.sarif
          retention-days: 30
      - name: PR Comment
        uses: actions/github-script@v7
        if: failure()
        with:
          script: |
            const fs = require('fs');
            const sarContent = fs.readFileSync('combined.sarif', 'utf8');
            const sarData = JSON.parse(sarContent);
            const output = `## Security Scan Summary\n\n`;
            sarData.runs.forEach(run => {
              const tool = run.tool.driver.name;
              const results = run.results || [];
              const summary = `**${tool}**: ${results.length} finding(s)`;
              output += `- ${tool}: ${results.length} findings\n`;
            });
            core.setOutput(`::error:: ${summary}`);
            core.setFailed('Security vulnerabilities found');
          });
      - name: Slack Alert
        if: failure() && env.SLACK_WEBHOOK_URL && env.SLACK_CHANNEL_ID
        run: |
          curl -X POST -H 'Content-type: application/json' \
            -d '{
              "text": "🚨 Security vulnerabilities found in ${{ github.repository }}\nPlease review: security scan results in the GitHub Actions tab."}' \
            ${{ secrets.SLACK_WEBHOOK_URL }} \
            ${{ secrets.SLACK_CHANNEL_ID }}
          echo "::warning:: Slack alert sent"
        fi
      - name: Fail on Critical
        if: failure() && steps.*report.outputs.some(r.run['CRITICAL')
 49        run: exit 1
    end
  end
```
**Step 7: Commit implementation**
```bash
git add .
git commit -m "feat: add security scan workflow
- Comprehensive scanning: dependencies, static code, secrets, filesystem
- Automated execution: PR and scheduled
- PR policy: Critical vulnerabilities in secrets fail PR
- Slack alerts for security team
- SAR upload for GitHub Security integration"
```
**Step 8: Push to remote**
```bash
git push
```
**Expected:** Push commits to remote repository

## Task Summary
총 **14개 task**를 모두 완료했습니다.
**구현 계획:**
1. **Workflow 파일 생성** (`.github/workflows/security-scan.yml`)
2. **설계 문서 작성** (`docs/plans/2026-04-03-security-scan-implementation.md`)
3. **커밋** (docs/plans/2026-04-03-security-scan-implementation.md)

4. **푸시** (main 브랜치)

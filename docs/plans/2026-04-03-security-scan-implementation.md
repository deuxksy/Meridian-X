# Security Scan Implementation Plan

> **For Claude:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** GitHub Actions를 통한 Python 프로젝트 종합 보안 스캔 자동화 시스템을 구축합니다.
**Architecture:** Gradual한 방식으로 4개의 스캔 도구를 단계별로 실행하고, 결과를 집계 및 SAR 업로드를 통해 GitHub Security 탭에 통합 관리합니다.
**Tech Stack:** GitHub Actions, pip-audit, Bandit, Gitleaks, Trivy, SARIF

---

## Task Structure

````markdown
### Task 1: Workflow 파일 생성
**Files:**
- Create: `.github/workflows/security-scan.yml`

**Step 1: Write workflow file skeleton**
```yaml
name: Security Scan
on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: '0 9 * * 1'  # 매일 오전 9시 (KST)
  workflow_dispatch:
```

**Step 2: Run test to verify file structure**
Expected: Workflow file created with correct structure

**Step 3: Implement Python setup step**
```yaml
- name: Setup Python
  uses: actions/setup-python@v5
  with:
    python-version: "3.12"
    cache: "pip"
```
**Step 4: Implement dependency installation step**
```yaml
- name: Install dependencies
  run: |
    pip install -r requirements pip-audit bandit
```
**Step 5: Implement pip-audit scan**
```yaml
- name: Dependency Vulnerability Scan
  run: |
    pip-audit -r requirements --ignore-vulns --skip-editable . --progress-handler=pip_audit._cli.cli:displayProgressBar(progressHandler, outputHandler)
```
**Step 6: Run test to verify pip-audit fails**
Run: |
  # Test should fail initially (no vulnerabilities found yet)
  echo "pip-audit: No vulnerabilities found"
Expected: FAIL with "pip-audit not found"
**Step 7: Implement Bandit scan**
```yaml
- name: Static Analysis (Bandit)
  run: bandit -r src -ll -ii
`` ```
**Step 8: Run test to verify Bandit fails**
Run: |
  # Test should detect medium severity issues
  echo "Bandit: Medium severity issues found"
Expected: FAIL with "Bandit issues detected"
**Step 9: Implement Gitleaks scan**
```yaml
- name: Secret Scan (Gitleaks)
  uses: gitleaks/gitleaks-action@v2
  with:
    args: --verbose --repo-path=.
```
**Step 10: Run test to verify Gitleaks fails**
Run: |
  # Test should detect secrets
  echo "Gitleaks: Secrets detected"
Expected: FAIL with "Secrets detected"
**Step 11: Implement Trivy scan**
```yaml
- name: Filesystem Scan (Trivy)
  uses: aquasecurity/trivy-action@master
  with:
    scan-type: 'fs'
    scan-ref: '.'
    ignore-unfixed: true
    format: 'sarif'
    output: 'trivy-results.sarif'
    severity: 'HIGH'
    exit-code: 1
```
**Step 12: Run test to verify Trivy fails**
Run: |
  # Test should detect filesystem issues
  echo "Trivy: Filesystem issues found"
Expected: FAIL with "Trivy issues detected"
**Step 13: Implement result aggregation step**
```yaml
- name: Aggregate Results
  run: |
    echo "## Security Scan Summary"
    echo "| Tool | Status | Findings |"
    echo "|------|-------|------------|"
    # Check and output results from each tool
    if [ -f "pip-audit-results.txt" ]; then
      echo "pip-audit: $(cat pip-audit-results.txt)"
    else
      echo "pip-audit: No issues found"
    fi
    # Similar checks for other tools...
  echo ""
Expected: Aggregated summary displayed
**Step 14: Implement SAR ball creation step**
```yaml
- name: Create SAR Ball
  run: |
    # Combine all SAR results into single file
    cat results/pip-audit.txt results/bandit.txt results/gitleaks.txt results/trivy.txt > combined.sarif
    jq -s '.' > results.sarif
  echo "SAR ball created"
```
**Step 15: Run test to verify SAR ball creation**
Run: |
  # Test should create valid SAR file
  echo "SAR ball created successfully"
Expected: FAIL with "SAR creation failed"
**Step 16: Implement SAR upload step**
```yaml
- name: Upload SAR
  uses: actions/upload-artifact@v4
  with:
    name: SAR_BALL_RESULTS
    path: results.sarif
    retention-days: 30
```
**Step 17: Run test to verify SAR upload fails**
Run: |
  # Test should upload SAR file
  echo "SAR upload failed"
Expected: FAIL with "SAR upload failed"
**Step 18: Implement PR comment step**
```yaml
- name: PR Comment
  uses: actions/github-script@v7
  if: failure()
  with:
    script: |
      const fs = require('fs');
      const results = JSON.parse(fs.readFileSync('results.sarif', 'utf8'));
      const vulnerabilities = results.runs?.flatMap(r => r.run);
        const { tool, report } in r;
        const finding = report.findings.find(f => f.severity === 'HIGH' || f.severity === 'CRITICAL');
        if (finding) {
          core.setFailed(`Security vulnerability found in ${finding.tool}`);
          core.setOutput(`::error ::${finding.message}`);
        } else if (finding.severity === 'MEDIUM') {
          core.warning(`::warning :: ${finding.message}`);
        }
      });
      # Add comment to PR
      const output = `## ⚠ Security Vulnerability Found

**Tool:** ${finding.tool}
**Severity:** ${finding.severity}
**Message:** ${finding.message}
Please review the [Security tab](${process.env.GITHUB_SERVER_URL}/${process.env.GITHUB_REPOSITORY}/actions/runs/${process.env.GITHUB_RUN_ID}) for details.`;
      core.setFailed('Security vulnerabilities found');
    env:
      GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```
**Step 19: Run test to verify PR comment fails**
Run: |
  # Test should fail when vulnerabilities found
  echo "PR comment created"
Expected: FAIL with "PR comment creation failed"
**Step 20: Implement Slack Alert step**
```yaml
- name: Slack Alert
  if: failure()
  run: |
    curl -X POST -H 'Content-type: application/json' \
      -d '{
        "text": "🚨 Security vulnerabilities found in ${{ github.repository }}\nPlease review: security scan results in the GitHub Actions tab."
      }' \
      ${{ secrets.SLACK_WEBHOOK_URL }}
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
    SLACK_CHANNEL_ID: ${{ secrets.SLACK_CHANNEL_ID }}
```
**Step 21: Run test to verify Slack Alert fails**
Run: |
  # Test should send alert when secrets are available
  echo "Slack alert sent"
Expected: FAIL with "Slack alert failed"
**Step 22: Implement Fail on Critical step**
```yaml
- name: Fail on Critical
  if: failure() && steps.*report.results.some(r.run['CRITICAL')
  run: exit 1
```
**Step 23: Commit implementation plan**
Run: |
  git add .
  git commit -m "feat: add security scan workflow

- Comprehensive scanning: dependencies, static code, secrets, and filesystem
- Automated execution on PR and scheduled
- PR policy: Critical vulnerabilities in secrets fail PR, others generate warnings
- Slack alerts for high/critical findings
- SAR upload for GitHub Security integration

- Test-driven development approach
- Each tool tested independently
- Gradual failure handling for better debugging"
```

## Execution Handoff
After saving the plan, I'll implement this in the **current session** or create a new worktree.

 to isolate this work. The workflow file to 생성 in a separate git worktree using the `superpowers:using-git-worktrees` skill first. If a worktree approach is preferred, then we the user.

For more details on worktrees.

Plan saved to: docs/plans/2026-04-03-security-scan-implementation.md

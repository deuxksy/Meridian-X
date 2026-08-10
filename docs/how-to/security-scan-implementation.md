# Security Scan 구현 가이드

이 문서는 Meridian-X의 GitHub Actions 보안 스캔 workflow를 확인·수정·검증하는 절차를 정리한다. 현재 구현 파일은 `.github/workflows/security-scan.yml`이다.

## 전제 조건

- Python 3.12 프로젝트
- GitHub Actions 사용 가능 repository
- `requirements.txt` 존재
- 선택: Slack 알림용 `vars.SLACK_WEBHOOK_URL`

## 1. Workflow 파일 확인

```bash
ls -la .github/workflows
sed -n '1,220p' .github/workflows/security-scan.yml
```

확인할 항목:

- `actions/checkout@v4`가 먼저 실행되는지
- `actions/setup-python@v5`가 Python 3.12를 사용하는지
- `pip-audit`, `bandit`, `gitleaks`, `trivy` 단계가 존재하는지
- SARIF artifact 업로드 단계가 존재하는지

## 2. 의존성 스캔 확인

현재 workflow는 다음 형태로 실행한다.

```bash
pip install pip-audit bandit
pip-audit -r requirements.txt || true
```

`|| true`가 있으므로 취약점이 발견되어도 workflow는 다음 단계로 진행한다. PR 차단 정책으로 전환하려면 `|| true`를 제거하고 예외 목록을 별도 관리한다.

## 3. 정적 분석 확인

```bash
bandit -r src -ll || true
```

`-ll`은 medium 이상 severity를 대상으로 한다. 현재는 관측 우선 정책이므로 실패를 강제하지 않는다.

## 4. Secret 스캔 확인

Gitleaks는 GitHub Action으로 실행한다.

```yaml
- name: Secret Scan (Gitleaks)
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Secret 탐지 정책은 action 기본 동작을 따른다. False positive가 발생하면 `.gitleaks.toml`에 allowlist를 추가한다.

## 5. Trivy SARIF 생성 확인

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
    exit-code: 0
```

`exit-code: 0`이므로 Trivy finding은 artifact로 남기고 workflow 실패 조건으로 사용하지 않는다.

## 6. Artifact 확인

Workflow 완료 후 GitHub Actions run의 artifact에서 `SAR_BALL_RESULTS`를 확인한다.

```text
SAR_BALL_RESULTS
└── combined.sarif
```

현재 `combined.sarif` 생성은 단순 SARIF append 방식이다. GitHub Code Scanning 업로드까지 확장하려면 SARIF JSON을 정식 merge해야 한다.

## 7. Slack 알림 설정

Slack 알림이 필요하면 repository variable에 webhook URL을 설정한다.

```text
Settings → Secrets and variables → Actions → Variables
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

현재 workflow 조건:

```yaml
if: failure() && vars.SLACK_WEBHOOK_URL != ''
```

따라서 workflow가 실패하고 variable이 설정된 경우에만 알림을 보낸다.

## 8. 로컬 검증

GitHub Actions와 완전히 동일하지는 않지만, 주요 scanner는 로컬에서 빠르게 확인할 수 있다.

```bash
uv run python --version
uv run pytest tests/ -v
uv run --with bandit bandit -r src -ll
```

`pip-audit`는 현재 workflow가 `requirements.txt`를 기준으로 실행하므로 아래 명령으로 확인한다.

```bash
uv run --with pip-audit pip-audit -r requirements.txt
```

## 개선 후보

- `requirements.txt`를 `uv export` 산출물로 관리하여 `pyproject.toml`/`uv.lock`과 drift를 줄인다.
- `pip-audit`와 `bandit`의 `|| true`를 제거해 PR 차단 정책을 강화한다.
- `combined.sarif`를 단순 append가 아니라 JSON merge로 생성한다.
- `github/codeql-action/upload-sarif`를 사용해 GitHub Code Scanning 탭에 업로드한다.

# SOPS + Age Binary Encryption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Encrypt `config/settings.json` in binary mode using `sops` and `age`, configure `.sops.yaml`, update `load_config()` in `src/meridian_x/core.py` to transparently decrypt and load binary-encrypted settings, and add unit tests.

**Architecture:** Create `.sops.yaml` for age key creation rule. Enhance `load_config()` to detect binary/encrypted content when `json.loads` fails, executing `sops --decrypt` via subprocess to obtain the JSON string. Add helper script `scripts/encrypt_settings.sh`.

**Tech Stack:** Python 3.10+, `sops`, `age`, `pytest`.

## Global Constraints
- SOPS Age key file location: `~/.config/sops/age/keys.txt`
- Age Public Key: `age1qw643dna4spaup6sr5ap0jf039ncjd54e8ekvrfy6p6x96ys2y4qn5vcsy`
- Strict binary mode flags for SOPS: `--input-type binary --output-type binary`

---

### Task 1: Create `.sops.yaml` configuration and helper script `scripts/encrypt_settings.sh`

**Files:**
- Create: `.sops.yaml`
- Create: `scripts/encrypt_settings.sh`

**Interfaces:**
- Consumes: `age` public key `age1qw643dna4spaup6sr5ap0jf039ncjd54e8ekvrfy6p6x96ys2y4qn5vcsy`
- Produces: `.sops.yaml` configuration and executable `scripts/encrypt_settings.sh` script

- [ ] **Step 1: Create `.sops.yaml` file**

Create `.sops.yaml`:
```yaml
creation_rules:
  - path_regex: config/settings\.json$
    age: age1qw643dna4spaup6sr5ap0jf039ncjd54e8ekvrfy6p6x96ys2y4qn5vcsy
```

- [ ] **Step 2: Create `scripts/encrypt_settings.sh` script**

Create `scripts/encrypt_settings.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SETTINGS_FILE="$PROJECT_ROOT/config/settings.json"
KEY_FILE="${SOPS_AGE_KEY_FILE:-$HOME/.config/sops/age/keys.txt}"

if [ ! -f "$KEY_FILE" ]; then
    echo "Error: Age key file not found at $KEY_FILE" >&2
    exit 1
fi

export SOPS_AGE_KEY_FILE="$KEY_FILE"

ACTION="${1:---encrypt}"

case "$ACTION" in
    --encrypt|-e)
        if [ ! -f "$SETTINGS_FILE" ]; then
            echo "Error: $SETTINGS_FILE does not exist." >&2
            exit 1
        fi
        echo "Encrypting $SETTINGS_FILE in binary mode..."
        TMP_FILE="$(mktemp)"
        sops --encrypt --input-type binary --output-type binary "$SETTINGS_FILE" > "$TMP_FILE"
        mv "$TMP_FILE" "$SETTINGS_FILE"
        echo "Successfully encrypted $SETTINGS_FILE."
        ;;
    --decrypt|-d)
        if [ ! -f "$SETTINGS_FILE" ]; then
            echo "Error: $SETTINGS_FILE does not exist." >&2
            exit 1
        fi
        echo "Decrypting $SETTINGS_FILE..."
        sops --decrypt --input-type binary --output-type binary "$SETTINGS_FILE"
        ;;
    *)
        echo "Usage: $0 [--encrypt|--decrypt]" >&2
        exit 1
        ;;
esac
```

chmod +x `scripts/encrypt_settings.sh`.

- [ ] **Step 3: Commit Task 1**

```bash
git add .sops.yaml scripts/encrypt_settings.sh
chmod +x scripts/encrypt_settings.sh
git commit -m "feat: .sops.yaml 설정 및 encrypt_settings.sh 스크립트 추가"
```

---

### Task 2: Update `load_config` in `src/meridian_x/core.py` to support SOPS binary decryption

**Files:**
- Modify: `src/meridian_x/core.py`
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: `config_path` (Path or string)
- Produces: `load_config(config_path: str | Path | None = None) -> dict` transparently handling both plain JSON and binary SOPS encrypted JSON.

- [ ] **Step 1: Write failing unit test in `tests/test_core.py`**

Add tests to `tests/test_core.py`:
```python
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
import pytest
from meridian_x.core import load_config

def test_load_config_encrypted(tmp_path):
    # Setup sample config
    config_file = tmp_path / "settings.json"
    raw_json = '{"sources": {"test": {"enabled": true}}}'
    config_file.write_text(raw_json, encoding="utf-8")
    
    # Encrypt using sops binary mode if sops is available
    sops_bin = shutil.which("sops")
    key_file = Path.home() / ".config" / "sops" / "age" / "keys.txt"
    
    if not sops_bin or not key_file.exists():
        pytest.skip("sops binary or age keys.txt not found")
        
    env = os.environ.copy()
    env["SOPS_AGE_KEY_FILE"] = str(key_file)
    
    enc_cmd = [
        sops_bin, "--encrypt",
        "--age", "age1qw643dna4spaup6sr5ap0jf039ncjd54e8ekvrfy6p6x96ys2y4qn5vcsy",
        "--input-type", "binary",
        "--output-type", "binary",
        str(config_file)
    ]
    res = subprocess.run(enc_cmd, capture_output=True, env=env)
    assert res.returncode == 0, f"Encryption failed: {res.stderr.decode()}"
    
    config_file.write_bytes(res.stdout)
    
    # Verify load_config decrypts transparently
    loaded = load_config(config_file)
    assert loaded == {"sources": {"test": {"enabled": True}}}
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_core.py -k test_load_config_encrypted -v`
Expected: FAIL (JSONDecodeError / UnicodeDecodeError when attempting standard `json.loads`)

- [ ] **Step 3: Implement transparent decryption in `src/meridian_x/core.py`**

Update `load_config` in `src/meridian_x/core.py`:
```python
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Set

logger = logging.getLogger(__name__)


def load_config(config_path: str | Path | None = None) -> dict:
    """
    config/settings.json에서 설정을 로드합니다.
    일반 JSON 및 sops 바이너리 암호화 파일을 모두 지원합니다.
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "settings.json"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        logger.error(f"Config not found: {config_path}")
        raise FileNotFoundError(f"Config not found: {config_path}")

    raw_bytes = config_path.read_bytes()

    # 1. 일반 UTF-8 JSON 파싱 시도
    try:
        raw_text = raw_bytes.decode("utf-8")
        return json.loads(raw_text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        # 2. 파싱 실패 시 SOPS 바이너리 복호화 시도
        logger.info(f"Attempting sops binary decryption for {config_path}")
        sops_bin = shutil.which("sops")
        if not sops_bin:
            logger.error("sops command not found for encrypted config")
            raise RuntimeError("sops command is required to load encrypted config")

        env = os.environ.copy()
        if "SOPS_AGE_KEY_FILE" not in env:
            default_key = Path.home() / ".config" / "sops" / "age" / "keys.txt"
            if default_key.exists():
                env["SOPS_AGE_KEY_FILE"] = str(default_key)

        cmd = [
            sops_bin,
            "--decrypt",
            "--input-type",
            "binary",
            "--output-type",
            "binary",
            str(config_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, env=env)
        if proc.returncode != 0:
            err_msg = proc.stderr.decode("utf-8", errors="replace")
            logger.error(f"Failed to decrypt config with sops: {err_msg}")
            raise ValueError(f"Failed to decrypt config with sops: {err_msg}")

        try:
            return json.loads(proc.stdout.decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to parse decrypted config JSON: {e}")
            raise ValueError(f"Decrypted config is not valid JSON: {e}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_core.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 2**

```bash
git add src/meridian_x/core.py tests/test_core.py
git commit -m "feat: load_config() sops 바이너리 암호화 자동 복호화 지원"
```

---

### Task 3: Encrypt `config/settings.json` and verify Meridian-X tests

**Files:**
- Modify: `config/settings.json`

- [ ] **Step 1: Encrypt `config/settings.json` using `scripts/encrypt_settings.sh`**

Run: `./scripts/encrypt_settings.sh --encrypt`

- [ ] **Step 2: Run full test suite to verify everything works with encrypted `config/settings.json`**

Run: `pytest`
Expected: ALL PASS

- [ ] **Step 3: Commit Task 3**

```bash
git add config/settings.json
git commit -m "chore: config/settings.json 바이너리 암호화 적용"
```

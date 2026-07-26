# Design Specification: SOPS + Age Binary Encryption for settings.json

## Overview
Encrypt `config/settings.json` using `sops` and `age` in binary format (`--input-type binary --output-type binary`), configure `.sops.yaml` for key management, and update `src/meridian_x/core.py:load_config()` to transparently decrypt and load binary-encrypted settings files.

## Key Components

### 1. `.sops.yaml` Configuration
Create `.sops.yaml` at project root (`/home/crong/git/Meridian-X/.sops.yaml`):
```yaml
creation_rules:
  - path_regex: config/settings\.json$
    age: age1qw643dna4spaup6sr5ap0jf039ncjd54e8ekvrfy6p6x96ys2y4qn5vcsy
```

### 2. Transparent Config Loading (`src/meridian_x/core.py`)
Modify `load_config(config_path)`:
1. Read raw bytes from `config_path`.
2. Try parsing bytes as UTF-8 JSON via `json.loads()`.
3. If `json.JSONDecodeError` or `UnicodeDecodeError` is caught:
   - Run `sops --decrypt --input-type binary --output-type binary <config_path>` via `subprocess.run()`.
   - Ensure `SOPS_AGE_KEY_FILE` environment variable defaults to `~/.config/sops/age/keys.txt` if present and not set.
   - Parse returned stdout bytes as JSON.
   - Return config dictionary.

### 3. Helper Script (`scripts/encrypt_settings.sh`)
Provide a shell script `scripts/encrypt_settings.sh` for convenient manual encryption/decryption of `config/settings.json`:
- Supports `--encrypt` (binary mode) and `--decrypt` (binary mode).

### 4. Testing & Verification
- Unit test in `tests/test_core.py` verifying:
  - Loading standard plain JSON `settings.json`.
  - Loading binary sops-encrypted `settings.json`.
  - Proper error handling when decryption fails or `sops` command fails.

## Isolation and Error Handling
- Normal plain JSON files continue to load instantly without invoking subprocesses.
- Binary encrypted files trigger `sops` decryption.
- If `sops` fails (e.g. key missing or bad format), `load_config()` raises `ValueError` / `RuntimeError` with informative error logging.

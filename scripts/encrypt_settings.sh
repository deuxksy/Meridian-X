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

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PLAIN_SETTINGS="$PROJECT_ROOT/config/settings.json"
ENCRYPTED_SETTINGS="$PROJECT_ROOT/config/settings.json.sops"
KEY_FILE="${SOPS_AGE_KEY_FILE:-$HOME/.config/sops/age/keys.txt}"

if [ ! -f "$KEY_FILE" ]; then
    echo "Error: Age key file not found at $KEY_FILE" >&2
    exit 1
fi

export SOPS_AGE_KEY_FILE="$KEY_FILE"

ACTION="${1:---encrypt}"

case "$ACTION" in
    --encrypt|-e)
        if [ ! -f "$PLAIN_SETTINGS" ]; then
            echo "Error: $PLAIN_SETTINGS does not exist." >&2
            exit 1
        fi
        echo "Encrypting $PLAIN_SETTINGS in binary mode to $ENCRYPTED_SETTINGS..."
        TMP_FILE="$(mktemp)"
        sops --encrypt --input-type binary --output-type binary "$PLAIN_SETTINGS" > "$TMP_FILE"
        mv "$TMP_FILE" "$ENCRYPTED_SETTINGS"
        echo "Successfully encrypted to $ENCRYPTED_SETTINGS."
        ;;
    --decrypt|-d)
        TARGET_FILE=""
        if [ -f "$ENCRYPTED_SETTINGS" ]; then
            TARGET_FILE="$ENCRYPTED_SETTINGS"
        elif [ -f "$PLAIN_SETTINGS" ]; then
            TARGET_FILE="$PLAIN_SETTINGS"
        else
            echo "Error: Neither $ENCRYPTED_SETTINGS nor $PLAIN_SETTINGS exists." >&2
            exit 1
        fi
        echo "Decrypting $TARGET_FILE to $PLAIN_SETTINGS..."
        TMP_FILE="$(mktemp)"
        sops --decrypt --input-type binary --output-type binary "$TARGET_FILE" > "$TMP_FILE"
        mv "$TMP_FILE" "$PLAIN_SETTINGS"
        echo "Successfully decrypted to $PLAIN_SETTINGS."
        ;;
    *)
        echo "Usage: $0 [--encrypt|--decrypt]" >&2
        exit 1
        ;;
esac

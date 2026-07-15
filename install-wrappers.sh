#!/bin/bash
# Symlinks every script in wrapper-scripts/ into ~/.local/bin/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER_DIR="$SCRIPT_DIR/wrapper-scripts"
TARGET_DIR="$HOME/.local/bin"

mkdir -p "$TARGET_DIR"

for script in "$WRAPPER_DIR"/*; do
    [ -f "$script" ] || continue
    chmod +x "$script"
    ln -sf "$script" "$TARGET_DIR/$(basename "$script")"
    echo "Linked $(basename "$script") -> $TARGET_DIR/$(basename "$script")"
done

case ":$PATH:" in
    *":$TARGET_DIR:"*) ;;
    *)
        echo
        echo "Note: $TARGET_DIR is not in your PATH."
        echo "Add this to your shell config (e.g. ~/.bashrc):"
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        ;;
esac

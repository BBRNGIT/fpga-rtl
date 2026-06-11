#!/bin/sh
# install_hooks.sh — install/refresh git hooks for this repo and the .hft vault.
#
# Idempotent: safe to run any number of times.
#
# 1. Main repo: copies the tracked hook source (hooks/pre-commit) into
#    .git/hooks/pre-commit. The tracked copy is the source of truth.
# 2. Vault (.hft): a standalone git repo (not a submodule). Its immutability
#    hook lives in .hft/.githooks/pre-commit; we point core.hooksPath at it.
set -e

repo_root=$(cd "$(dirname "$0")" && pwd)
cd "$repo_root"

# --- 1. Main repo pre-commit hook ------------------------------------------
src="$repo_root/hooks/pre-commit"
dst="$repo_root/.git/hooks/pre-commit"

if [ ! -f "$src" ]; then
    echo "[FAIL] missing tracked hook source: hooks/pre-commit" >&2
    exit 1
fi

if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
    echo "[ok] .git/hooks/pre-commit already up to date"
else
    cp "$src" "$dst"
    echo "[ok] installed .git/hooks/pre-commit from hooks/pre-commit"
fi
chmod +x "$dst"

# --- 2. Vault (.hft) immutability hook --------------------------------------
if [ -d "$repo_root/.hft/.git" ] || [ -f "$repo_root/.hft/.git" ]; then
    if [ -f "$repo_root/.hft/.githooks/pre-commit" ]; then
        chmod +x "$repo_root/.hft/.githooks/pre-commit"
        current=$(git -C "$repo_root/.hft" config --get core.hooksPath || true)
        if [ "$current" = ".githooks" ]; then
            echo "[ok] .hft core.hooksPath already set to .githooks"
        else
            git -C "$repo_root/.hft" config core.hooksPath .githooks
            echo "[ok] set .hft core.hooksPath = .githooks (immutability guard active)"
        fi
    else
        echo "[warn] .hft/.githooks/pre-commit not found — vault immutability guard NOT installed" >&2
    fi
else
    echo "[warn] .hft is not a git repo — skipping vault hook setup" >&2
fi

echo "[done] hooks installed"

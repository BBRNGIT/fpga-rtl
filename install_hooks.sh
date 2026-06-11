#!/bin/sh
# install_hooks.sh — install/refresh git hooks for this repo and the .hft vault.
#
# Idempotent: safe to run any number of times.
#
# 1. Main repo: copies the tracked hook sources (hooks/pre-commit, hooks/commit-msg)
#    into .git/hooks/. The tracked copies are the source of truth. Attribution is
#    checked by commit-msg (the only hook git gives the message to); pre-commit
#    does the file-level checks (vault immutability, thin-test, gen byte-match).
# 2. Vault (.hft): a standalone git repo (not a submodule). Its immutability
#    hook lives in .hft/.githooks/pre-commit; we point core.hooksPath at it.
set -e

repo_root=$(cd "$(dirname "$0")" && pwd)
cd "$repo_root"

# --- 1. Main repo hooks (pre-commit + commit-msg) --------------------------
for hook in pre-commit commit-msg; do
    src="$repo_root/hooks/$hook"
    dst="$repo_root/.git/hooks/$hook"
    if [ ! -f "$src" ]; then
        echo "[FAIL] missing tracked hook source: hooks/$hook" >&2
        exit 1
    fi
    if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
        echo "[ok] .git/hooks/$hook already up to date"
    else
        cp "$src" "$dst"
        echo "[ok] installed .git/hooks/$hook from hooks/$hook"
    fi
    chmod +x "$dst"
done

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

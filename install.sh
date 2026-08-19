#!/usr/bin/env bash
# Awesome-Janson 一鍵安裝腳本
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="${HOME}/.claude/skills"

echo "🎬 正在安裝【剪神 / Awesome-Janson】..."

mkdir -p "${SKILLS_DIR}"
ln -sfn "${SCRIPT_DIR}" "${SKILLS_DIR}/awesome-janson"

# 若存在 .agents/skills 也同步建立
if [ -d "${HOME}/.agents/skills" ]; then
  ln -sfn "${SCRIPT_DIR}" "${HOME}/.agents/skills/awesome-janson"
fi

if [ -d "${HOME}/.codex/skills" ]; then
  ln -sfn "${SCRIPT_DIR}" "${HOME}/.codex/skills/awesome-janson"
fi

echo "✅ 安裝成功！已將 Awesome-Janson 連結至 AI Agent Skills。"
echo "💡 執行 python3 ${SCRIPT_DIR}/scripts/doctor.py 檢查剪輯環境。"

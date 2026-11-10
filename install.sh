#!/usr/bin/env bash
# Install one or more skills from this repository into an agent skills directory.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="claud"
DEST=""
FORCE=0
LIST=0
SKILLS=()

usage() {
  cat <<'USAGE'
用法: ./install.sh [skill ...] [选项]

不指定 skill 时安装仓库中的全部 skill。

选项:
  -t, --target <name>  目标 agent: claud | codex | agents | cc-switch (默认: claud)
  -d, --dest <path>    自定义安装目录（优先于 --target）
  -f, --force          已存在时覆盖
  -l, --list           列出仓库中的 skill
  -h, --help           显示帮助

示例:
  ./install.sh
  ./install.sh multi-bot-adapter
  ./install.sh --target codex secure-system-development
  ./install.sh --dest "/path/to/project/.Claud/skills"
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -t|--target) TARGET="${2:?缺少 --target 的值}"; shift 2 ;;
    -d|--dest)   DEST="${2:?缺少 --dest 的值}"; shift 2 ;;
    -f|--force)  FORCE=1; shift ;;
    -l|--list)   LIST=1; shift ;;
    -h|--help)   usage; exit 0 ;;
    --all)       SKILLS=(); shift ;;
    -*)          echo "未知选项: $1" >&2; usage; exit 2 ;;
    *)           SKILLS+=("$1"); shift ;;
  esac
done

AVAILABLE=()
for dir in "$ROOT"/*/; do
  [[ -f "${dir}SKILL.md" ]] && AVAILABLE+=("$(basename "$dir")")
done

if [[ $LIST -eq 1 ]]; then
  printf '可用 skill:\n'
  for name in "${AVAILABLE[@]}"; do
    version="$(grep -m1 '^version:' "$ROOT/$name/SKILL.md" | sed -E 's/^version:[[:space:]]*"?([^"]*)"?.*/\1/')"
    printf '  %-28s %s\n' "$name" "$version"
  done
  exit 0
fi

if [[ -z "$DEST" ]]; then
  case "$TARGET" in
    claud)
      if [[ -d "$HOME/.Claud" ]]; then DEST="$HOME/.Claud/skills"
      else DEST="$HOME/.claud/skills"; fi ;;
    codex)     DEST="$HOME/.codex/skills" ;;
    agents)    DEST="$HOME/.agents/skills" ;;
    cc-switch) DEST="$HOME/.cc-switch/skills" ;;
    *) echo "未知目标: $TARGET（可选 claud|codex|agents|cc-switch）" >&2; exit 2 ;;
  esac
fi

if [[ ${#SKILLS[@]} -eq 0 ]]; then
  SKILLS=("${AVAILABLE[@]}")
fi

for name in "${SKILLS[@]}"; do
  src="$ROOT/$name"
  if [[ ! -f "$src/SKILL.md" ]]; then
    echo "未知 skill: $name" >&2
    echo "可用: ${AVAILABLE[*]}" >&2
    exit 2
  fi

  out="$DEST/$name"
  if [[ -e "$out" ]]; then
    if [[ $FORCE -eq 1 ]]; then
      rm -rf "$out"
    else
      echo "已存在: $out（使用 --force 覆盖）" >&2
      exit 1
    fi
  fi

  mkdir -p "$out"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a \
      --exclude 'dist/' --exclude '.git/' --exclude '__pycache__/' \
      --exclude '.pytest_cache/' --exclude '.DS_Store' --exclude 'Thumbs.db' \
      "$src/" "$out/"
  else
    ( cd "$src" && tar \
      --exclude='./dist' --exclude='./.git' --exclude='*/__pycache__' \
      --exclude='./__pycache__' --exclude='./.pytest_cache' \
      --exclude='./.DS_Store' --exclude='./Thumbs.db' -cf - . ) | ( cd "$out" && tar -xf - )
  fi
  echo "已安装 $name -> $out"
done

echo "完成。重启 agent 会话后生效。"

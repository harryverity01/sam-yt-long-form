#!/usr/bin/env bash
# sam-yt-skills installer
# Symlinks the 4 skills into ~/.claude/skills/, installs Python deps,
# prompts for API keys.

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$HOME/.claude/skills"

echo "▶ sam-yt-skills installer"
echo "  Repo: $REPO_DIR"
echo ""

# 1. Check system deps
echo "▶ Checking system dependencies..."
MISSING=()
for cmd in ffmpeg ffprobe python3; do
    if ! command -v $cmd >/dev/null 2>&1; then
        MISSING+=("$cmd")
    fi
done
if [ ${#MISSING[@]} -gt 0 ]; then
    echo "❌ Missing required commands: ${MISSING[*]}"
    echo "   Install via: brew install ffmpeg python@3.11"
    exit 1
fi
echo "✓ ffmpeg, ffprobe, python3 found"

# Optional deps
for cmd in yt-dlp gallery-dl; do
    if command -v $cmd >/dev/null 2>&1; then
        echo "✓ $cmd found (optional)"
    else
        echo "⚠️  $cmd not found (needed for some b-roll sources). Install: brew install $cmd"
    fi
done
echo ""

# 2. Python deps
echo "▶ Installing Python dependencies..."
if command -v uv >/dev/null 2>&1; then
    (cd "$REPO_DIR" && uv sync)
else
    python3 -m pip install --user -r "$REPO_DIR/requirements.txt"
fi
echo "✓ Python deps installed"
echo ""

# 3. Symlink skills
echo "▶ Installing skills to $SKILLS_DIR..."
mkdir -p "$SKILLS_DIR"
for skill in sam-yt-pipeline sam-yt-cutter sam-yt-broll-director sam-yt-broll-producer; do
    target="$SKILLS_DIR/$skill"
    if [ -e "$target" ] && [ ! -L "$target" ]; then
        echo "❌ $target exists and is not a symlink — refusing to overwrite"
        echo "   Move/remove it first, then re-run."
        exit 1
    fi
    rm -f "$target"
    ln -s "$REPO_DIR/skills/$skill" "$target"
    echo "  ✓ $skill"
done
echo ""

# 4. API keys
ENV_FILE="$REPO_DIR/.env"
echo "▶ API keys..."
if [ -f "$ENV_FILE" ]; then
    echo "✓ $ENV_FILE already exists"
else
    cp "$REPO_DIR/.env.example" "$ENV_FILE"
    echo "✓ Created $ENV_FILE from .env.example"
    echo ""
    echo "  Edit $ENV_FILE and add:"
    echo "    ELEVENLABS_API_KEY=...    (required for transcription + music)"
    echo "    FAL_KEY=...                (optional, for Seedance b-roll)"
    echo "    PEXELS_API_KEY=...         (optional, for stock b-roll)"
fi
echo ""

# 5. Verify install
echo "▶ Verifying install..."
if [ -d "$SKILLS_DIR/sam-yt-pipeline" ] && [ -f "$SKILLS_DIR/sam-yt-pipeline/SKILL.md" ]; then
    echo "✓ All 4 skills installed"
else
    echo "❌ Install verification failed"
    exit 1
fi
echo ""

echo "✅ Done."
echo ""
echo "Try it:"
echo "  1. mkdir ~/MyInterview && mkdir ~/MyInterview/raw"
echo "  2. Copy your camera files into ~/MyInterview/raw/"
echo "  3. In Claude Code:  /sam-yt-pipeline ~/MyInterview"
echo ""
echo "Docs: $REPO_DIR/README.md"

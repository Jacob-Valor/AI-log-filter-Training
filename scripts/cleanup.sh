#!/bin/bash
# =============================================================================
# AI Log Filter - Cleanup Script
# =============================================================================
# Safe cleanup script to remove unnecessary files and directories
# BEFORE RUNNING: Review the files being removed!
# =============================================================================

set -e  # Exit on error

echo "========================================"
echo "AI Log Filter - Project Cleanup Script"
echo "========================================"
echo ""
echo "This script will remove unnecessary files to reduce project size."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to format size
format_size() {
    if [ $1 -ge 1073741824 ]; then
        echo "scale=2; $1/1073741824" | bc | xargs echo "GB"
    elif [ $1 -ge 1048576 ]; then
        echo "scale=2; $1/1048576" | bc | xargs echo "MB"
    elif [ $1 -ge 1024 ]; then
        echo "scale=2; $1/1024" | bc | xargs echo "KB"
    else
        echo "$1 bytes"
    fi
}

# Calculate total space to be freed
echo "Calculating space savings..."
echo ""

# High-priority items (safe to remove)
HIGH_PRIORITY=(
    ".venv"
    "HDFS_v3_TraceBench.zip"
    "htmlcov"
    ".coverage"
    ".pytest_cache"
    "src/__pycache__"
    "tests/__pycache__"
)

# Get total size of high-priority items
TOTAL_SIZE=0
for item in "${HIGH_PRIORITY[@]}"; do
    if [ -e "$item" ]; then
        SIZE=$(du -sb "$item" 2>/dev/null | cut -f1)
        TOTAL_SIZE=$((TOTAL_SIZE + SIZE))
        FORMATTED=$(format_size $SIZE)
        echo -e "${GREEN}✓${NC} $item ($FORMATTED)"
    fi
done

# Empty directories to remove
EMPTY_DIRS=(
    "src/core/config"
    "src/core/exceptions"
    "src/core/logging"
    "src/data/ingestion"
    "src/data/postprocessing"
    "src/data/preprocessing"
    "src/serving/api"
    "src/serving/batch"
    "src/serving/streaming"
    "configs/environments"
    "configs/system"
    "configs/models"
    "docs/api"
    "docs/user-guide"
    "docs/compliance"
    "artifacts/models"
    "artifacts/experiments"
    "tests/unit"
    "tests/integration"
    "tests/e2e"
    "notebooks"
)

echo ""
echo "Empty directories to remove:"
for dir in "${EMPTY_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo -e "${YELLOW}○${NC} $dir/"
    fi
done

# Low-priority items (optional)
LOW_PRIORITY=(
    "HDFS_v3_TraceBench"
    "session-ses_4449.md"
    "README"
    "deploy"
    "data/samples"
)

echo ""
echo "Low-priority items (optional):"
for item in "${LOW_PRIORITY[@]}"; do
    if [ -e "$item" ]; then
        SIZE=$(du -sb "$item" 2>/dev/null | cut -f1)
        FORMATTED=$(format_size $SIZE)
        echo -e "${YELLOW}?${NC} $item ($FORMATTED)"
    fi
done

echo ""
echo "========================================"
echo -e "${GREEN}Total space to be freed (high-priority): $(format_size $TOTAL_SIZE)${NC}"
echo "========================================"
echo ""

# Ask for confirmation
read -p "Do you want to proceed with cleanup? (y/n): " confirm

if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Cleaning up..."
echo ""

# Remove high-priority items
for item in "${HIGH_PRIORITY[@]}"; do
    if [ -e "$item" ]; then
        rm -rf "$item"
        echo -e "${GREEN}✓${NC} Removed: $item"
    fi
done

# Remove empty directories
for dir in "${EMPTY_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        rmdir "$dir" 2>/dev/null || rm -rf "$dir"
        echo -e "${GREEN}✓${NC} Removed directory: $dir/"
    fi
done

# Ask about low-priority items
echo ""
read -p "Remove low-priority items? (y/n): " confirm2

if [ "$confirm2" == "y" ] || [ "$confirm2" == "Y" ]; then
    for item in "${LOW_PRIORITY[@]}"; do
        if [ -e "$item" ]; then
            rm -rf "$item"
            echo -e "${GREEN}✓${NC} Removed: $item"
        fi
    done
fi

echo ""
echo "========================================"
echo -e "${GREEN}Cleanup complete!${NC}"
echo "========================================"
echo ""
echo "Project size reduced. You can now rebuild with:"
echo "  1. python -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'"
echo "  2. Or use Docker: docker-compose build"
echo ""

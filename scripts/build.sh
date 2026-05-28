#!/bin/bash
set -e

# Directory setup
DIST_DIR="dist"
ARTIFACT_NAME="deploy.zip"
OUTPUT_PATH="$DIST_DIR/$ARTIFACT_NAME"

# Colors for output
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting build process...${NC}"

# Ensure dist directory exists
mkdir -p "$DIST_DIR"

# Clean old artifact
if [ -f "$OUTPUT_PATH" ]; then
    echo "removing old artifact: $OUTPUT_PATH"
    rm "$OUTPUT_PATH"
fi

echo "Creating zip artifact: $OUTPUT_PATH"

# Zip command with exclusions
# -r: recursive
# -x: exclude patterns
zip -r "$OUTPUT_PATH" . \
  -x "*.git*" \
  -x "*__pycache__*" \
  -x "*.venv*" \
  -x ".env" \
  -x "*.pyc" \
  -x "*.zip" \
  -x ".DS_Store" \
  -x "*.egg-info*" \
  -x "web_log_*" \
  -x "webapp_logs" \
  -x "*.md" \
  -x "archive/*" \
  -x "dist/*" \
  -x "tests/*" \
  -x "docs/*" \
  -x "examples/*" \
  -x "terminals/*" \
  -x ".cursor/*" \
  -x "startup_check_*" \
  -x "startup_monitor*" \
  -x "verify_multispace*"

echo -e "${GREEN}Build complete! Artifact ready at: $OUTPUT_PATH${NC}"
ls -lh "$OUTPUT_PATH"

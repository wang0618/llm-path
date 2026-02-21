#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

VERSION=$1

if [ -z "$VERSION" ]; then
    echo "Usage: ./scripts/release.sh <version>"
    echo "Example: ./scripts/release.sh 0.2.0"
    exit 1
fi

# Validate version format (basic semver check)
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
    echo "Error: Invalid version format. Expected semver (e.g., 0.2.0 or 0.2.0-beta.1)"
    exit 1
fi

echo "Building release $VERSION..."

cd "$PROJECT_ROOT"

# 1. Generate version file
echo "Step 1: Generating version file..."
echo "__version__ = \"$VERSION\"" > llm_path/_version.py

# 2. Build frontend
echo "Step 2: Building frontend..."
cd viewer
npm install --silent
npm run build

# 3. Copy to Python package
echo "Step 3: Copying frontend to Python package..."
rm -rf ../llm_path/viewer_dist
cp -r dist ../llm_path/viewer_dist

# 4. Build release package
echo "Step 4: Building release package..."
cd "$PROJECT_ROOT"
uv build

echo ""
echo "Release $VERSION built successfully!"
echo "Output: dist/"
ls -la dist/
echo ""
echo "To publish to PyPI: uv publish"

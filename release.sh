#!/bin/bash
# Create GitHub release using notes from release.txt

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NOTES_FILE="$SCRIPT_DIR/release.txt"

if [ ! -f "$NOTES_FILE" ]; then
    echo "Error: $NOTES_FILE not found"
    echo "Create release.txt with release notes"
    exit 1
fi

if [ ! -s "$NOTES_FILE" ]; then
    echo "Error: release.txt is empty"
    exit 1
fi

cd "$SCRIPT_DIR"

# Get latest tag and increment
LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
echo "Latest tag: $LATEST_TAG"

# Parse version and increment patch
if [[ $LATEST_TAG =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
    MAJOR="${BASH_REMATCH[1]}"
    MINOR="${BASH_REMATCH[2]}"
    PATCH="${BASH_REMATCH[3]}"
    NEW_TAG="v$MAJOR.$MINOR.$((PATCH + 1))"
else
    NEW_TAG="v1.0.0"
fi

echo "New tag: $NEW_TAG"
read -p "Proceed with release $NEW_TAG? [y/N] " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ">>> Creating release $NEW_TAG..."
    gh release create "$NEW_TAG" --title "$NEW_TAG" --notes-file "$NOTES_FILE"
    echo ">>> Done!"
else
    echo "Cancelled"
fi

#!/bin/bash
# Commit and push changes using message from commit.txt

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MSG_FILE="$SCRIPT_DIR/commit.txt"

if [ ! -f "$MSG_FILE" ]; then
    echo "Error: $MSG_FILE not found"
    echo "Create commit.txt with your commit message"
    exit 1
fi

if [ ! -s "$MSG_FILE" ]; then
    echo "Error: commit.txt is empty"
    exit 1
fi

cd "$SCRIPT_DIR"

echo ">>> Adding all changes..."
git add -A

echo ">>> Committing..."
git commit -F "$MSG_FILE"

if [ $? -eq 0 ]; then
    echo ">>> Pushing..."
    git push
    echo ">>> Done!"
else
    echo ">>> Nothing to commit or commit failed"
fi

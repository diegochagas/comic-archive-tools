#!/usr/bin/env bash
# Background batch generator: generates a list of pages sequentially, logging each.
# Usage: batch_gen.sh <project> <issue> <page1> [page2] ...
# Survives shell timeouts (run via setsid nohup ... &). Writes work/<issue>/gen/page_NN_try1.png
source ~/hf-env/env.sh
cd /sessions/adoring-practical-pascal/mnt/ai-comics
PROJECT="$1"; ISSUE="$2"; shift 2
LOG="projects/$PROJECT/work/$ISSUE/batch.log"
mkdir -p "projects/$PROJECT/work/$ISSUE"
echo "=== batch start $(date +%H:%M:%S) pages: $* ===" >> "$LOG"
for p in "$@"; do
  echo "--- page $p start $(date +%H:%M:%S) ---" >> "$LOG"
  out=$(python3 pipeline/gen_page.py "$PROJECT" "$ISSUE" "$p" 1 2>&1)
  echo "page $p -> $out" >> "$LOG"
done
echo "=== batch done $(date +%H:%M:%S) ===" >> "$LOG"

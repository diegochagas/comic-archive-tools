#!/bin/bash
# Runs detect_text.py on whatever pages in IMG_DIR don't yet have a
# detect_dir/<stem>_detect.json, until the caller's timeout kills it.
# Re-run repeatedly (each call picks up where the last one was cut off).
set -e
cd /sessions/wonderful-adoring-dijkstra/mnt/comic-ai-tools
IMG_DIR=/sessions/wonderful-adoring-dijkstra/mnt/Downloads/Japanese
OUT_DIR=$IMG_DIR/psd
DONE=$(ls "$OUT_DIR"/detect/*_detect.json 2>/dev/null | xargs -n1 basename | sed 's/_detect.json//' | sort)
ALL=$(cd "$IMG_DIR" && ls *.jpg | sed 's/\.jpg$//' | sort)
REMAIN=$(comm -23 <(echo "$ALL") <(echo "$DONE"))
N=$(echo -n "$REMAIN" | grep -c . || true)
echo "remaining before this round: $N"
if [ "$N" -eq 0 ]; then echo "ALL_DONE"; exit 0; fi
FILES=$(echo "$REMAIN" | sed "s#^#$IMG_DIR/#; s#\$#.jpg#" | tr '\n' ' ')
python3 scripts/detect_text.py "$OUT_DIR" $FILES

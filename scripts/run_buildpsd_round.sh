#!/bin/bash
# Builds Original+Cleaned PSDs (via build_psd_no_gimp.mjs) for every page that
# has a detect_text.py output but no PSD yet. One node process per page (each
# large-image decode is memory-heavy; a fresh process per page avoids OOM from
# accumulating heap across pages). Re-run repeatedly until ALL_DONE.
cd /sessions/wonderful-adoring-dijkstra/mnt/comic-ai-tools
IMG_DIR=/sessions/wonderful-adoring-dijkstra/mnt/Downloads/Japanese
OUT_DIR=$IMG_DIR/psd
DONE=$(ls "$OUT_DIR"/*.psd 2>/dev/null | xargs -n1 basename | sed 's/\.psd$//' | sort)
DETECTED=$(ls "$OUT_DIR"/detect/*_detect.json 2>/dev/null | xargs -n1 basename | sed 's/_detect.json//' | sort)
REMAIN=$(comm -23 <(echo "$DETECTED") <(echo "$DONE"))
N=$(echo -n "$REMAIN" | grep -c . || true)
echo "remaining before this round: $N"
if [ "$N" -eq 0 ]; then echo "ALL_DONE"; exit 0; fi
for stem in $REMAIN; do
  node scripts/build_psd_no_gimp.mjs "$OUT_DIR" "$stem:$IMG_DIR/$stem.jpg"
done

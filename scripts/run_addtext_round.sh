#!/bin/bash
# Adds placeholder text-box layers (add_text_layers.mjs) to every PSD that
# doesn't have any "Text N" layers yet. One node process per page (memory
# safety for large PSDs). Re-run repeatedly until ALL_DONE.
cd /sessions/wonderful-adoring-dijkstra/mnt/comic-ai-tools
IMG_DIR=/sessions/wonderful-adoring-dijkstra/mnt/Downloads/Japanese
OUT_DIR=$IMG_DIR/psd
ALL_PSD=$(ls "$OUT_DIR"/*.psd 2>/dev/null | xargs -n1 basename | sed 's/\.psd$//' | sort)
DONE=$(ls "$OUT_DIR"/*.textboxed 2>/dev/null | xargs -n1 basename | sed 's/\.textboxed$//' | sort)
REMAIN=$(comm -23 <(echo "$ALL_PSD") <(echo "$DONE"))
N=$(echo -n "$REMAIN" | grep -c . || true)
echo "remaining before this round: $N"
if [ "$N" -eq 0 ]; then echo "ALL_DONE"; exit 0; fi
for stem in $REMAIN; do
  node scripts/add_text_layers.mjs "$OUT_DIR" "$stem" && touch "$OUT_DIR/$stem.textboxed"
done

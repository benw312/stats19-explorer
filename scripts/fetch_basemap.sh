#!/bin/sh
# Fetch a self-hosted OpenStreetMap basemap (Protomaps PMTiles) for Great Britain,
# plus the fonts/sprites the Protomaps style needs, so the map works with no
# external requests (PLAN-004 D1).
#
# Usage: scripts/fetch_basemap.sh [OUT_DIR]   (default: data/basemap)
# Env:   BBOX (default GB), MAXZOOM (default 15), BUILD (default: latest),
#        FONTS_ONLY=1 to refresh just the fonts and sprites (no tile download)
# Downloads retry 3 times (e.g. a brief 503 from GitHub Pages).
# Needs: pmtiles CLI (brew install pmtiles) or Docker (uses protomaps/go-pmtiles).
set -eu

OUT_DIR="${1:-data/basemap}"
BBOX="${BBOX:--8.7,49.8,1.9,60.95}"
MAXZOOM="${MAXZOOM:-15}"
ASSETS="https://protomaps.github.io/basemaps-assets"
FONTS="Noto%20Sans%20Regular Noto%20Sans%20Medium Noto%20Sans%20Italic"
# Every 256-codepoint glyph range: labels for places abroad (seen at national zoom)
# can carry local names in Greek, Cyrillic, Arabic, Tifinagh... (~30 MB in all).
RANGES=$(python3 -c "print(' '.join(f'{i}-{i + 255}' for i in range(0, 65536, 256)))")

mkdir -p "$OUT_DIR/fonts" "$OUT_DIR/sprites"

if [ -n "${FONTS_ONLY:-}" ]; then
    echo "fonts and sprites only"
elif [ -z "${BUILD:-}" ]; then
    BUILD=$(curl -fsS --retry 3 --retry-delay 5 https://build-metadata.protomaps.dev/builds.json |
        python3 -c "import json,sys; print(json.load(sys.stdin)[-1]['key'])")
fi

if [ -z "${FONTS_ONLY:-}" ]; then
echo "basemap build: $BUILD  bbox: $BBOX  maxzoom: $MAXZOOM"

if command -v pmtiles >/dev/null 2>&1; then
    PMTILES="pmtiles"
    TARGET="$OUT_DIR/gb.pmtiles.part"
else
    # CDPATH= : with CDPATH set, cd prints the directory, which would end up in the -v value
    PMTILES="docker run --rm -v $(CDPATH= cd "$OUT_DIR" && pwd):/out protomaps/go-pmtiles"
    TARGET="/out/gb.pmtiles.part"
fi
$PMTILES extract "https://build.protomaps.com/$BUILD" "$TARGET" --bbox="$BBOX" --maxzoom="$MAXZOOM"
mv "$OUT_DIR/gb.pmtiles.part" "$OUT_DIR/gb.pmtiles"
echo "$BUILD" > "$OUT_DIR/BUILD"
fi

for font in $FONTS; do
    dir="$OUT_DIR/fonts/$(printf '%b' "$(echo "$font" | sed 's/%20/ /g')")"
    mkdir -p "$dir"
    for range in $RANGES; do
        # not every range exists for every font; skip the ones the server lacks
        curl -fsS --retry 3 --retry-delay 5 -o "$dir/$range.pbf" "$ASSETS/fonts/$font/$range.pbf" 2>/dev/null || rm -f "$dir/$range.pbf"
    done
    echo "$(ls "$dir" | wc -l | tr -d ' ') glyph ranges: $dir"
done

for theme in light; do
    for suffix in .json .png @2x.json @2x.png; do
        curl -fsS --retry 3 --retry-delay 5 -o "$OUT_DIR/sprites/$theme$suffix" "$ASSETS/sprites/v4/$theme$suffix"
    done
done

echo "done: $(du -sh "$OUT_DIR" | cut -f1) in $OUT_DIR"

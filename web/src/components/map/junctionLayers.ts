/**
 * Junctions built from OS Open Roads (PLAN-008 T3), from street zoom (z13).
 *
 * A junction is a place, not a collision, so it's drawn in ink rather than a severity hue:
 * a hollow ring sized by the junction collisions that match the current filter. Junctions
 * with none stay as small faint rings, so engineers can still open them (peer comparisons
 * need the quiet junctions too). Collision points draw on top and win the click.
 */
import type { Map as MlMap } from 'maplibre-gl'

import type { ApiFilter } from '../../lib/filter'
import { junctionTileUrl } from '../../lib/junctions'

export const JUNCTION_SOURCE = 'junctions'
export const JUNCTION_RINGS = 'junction-rings'
const JUNCTION_SELECTED = 'junction-selected'
const JUNCTION_LAYERS = [JUNCTION_RINGS, JUNCTION_SELECTED] as const
export const JUNCTION_MIN_ZOOM = 13

const INK = '#1c2126'
const ACCENT = '#0a6b45'

const sqrtN = ['sqrt', ['coalesce', ['get', 'n'], 0]]
const radius = (extra: number) =>
  [
    'interpolate',
    ['linear'],
    ['zoom'],
    13,
    ['interpolate', ['linear'], sqrtN, 0, 3 + extra, 1, 5 + extra, 6, 12 + extra],
    17,
    ['interpolate', ['linear'], sqrtN, 0, 6 + extra, 1, 9 + extra, 6, 22 + extra],
  ] as never

export function addJunctionLayers(m: MlMap, filter: ApiFilter, visible: boolean, beforeId?: string): void {
  const visibility = visible ? 'visible' : 'none'
  m.addSource(JUNCTION_SOURCE, {
    type: 'vector',
    tiles: [junctionTileUrl(filter)],
    minzoom: JUNCTION_MIN_ZOOM,
    maxzoom: 16,
  })
  m.addLayer(
    {
      id: JUNCTION_RINGS,
      type: 'circle',
      source: JUNCTION_SOURCE,
      'source-layer': 'junctions',
      minzoom: JUNCTION_MIN_ZOOM,
      layout: { visibility, 'circle-sort-key': ['coalesce', ['get', 'n'], 0] as never },
      paint: {
        'circle-radius': radius(0),
        'circle-color': '#ffffff',
        'circle-opacity': ['case', ['>', ['get', 'n'], 0], 0.55, 0.25] as never,
        'circle-stroke-color': INK,
        'circle-stroke-opacity': ['case', ['>', ['get', 'n'], 0], 0.85, 0.35] as never,
        'circle-stroke-width': ['case', ['>', ['get', 'n'], 0], 1.75, 1] as never,
      },
    },
    beforeId,
  )
  m.addLayer({
    id: JUNCTION_SELECTED,
    type: 'circle',
    source: JUNCTION_SOURCE,
    'source-layer': 'junctions',
    minzoom: JUNCTION_MIN_ZOOM,
    filter: ['==', ['get', 'id'], ''],
    layout: { visibility },
    paint: {
      'circle-radius': radius(4),
      'circle-color': 'rgba(0,0,0,0)',
      'circle-stroke-color': ACCENT,
      'circle-stroke-width': 3,
    },
  })
}

/** Traffic view: rings stay one size (no collisions there); otherwise sized by collisions. */
export function setJunctionRingsByCollisions(m: MlMap, byCollisions: boolean): void {
  if (!m.getLayer(JUNCTION_RINGS)) return
  const quiet = (busy: number, still: number) =>
    (byCollisions ? ['case', ['>', ['get', 'n'], 0], busy, still] : busy) as never
  m.setPaintProperty(JUNCTION_RINGS, 'circle-radius', byCollisions ? radius(0) : UNIFORM_RADIUS)
  m.setPaintProperty(JUNCTION_RINGS, 'circle-opacity', quiet(0.55, 0.25))
  m.setPaintProperty(JUNCTION_RINGS, 'circle-stroke-opacity', quiet(0.85, 0.35))
  m.setPaintProperty(JUNCTION_RINGS, 'circle-stroke-width', quiet(1.75, 1))
}

const UNIFORM_RADIUS = ['interpolate', ['linear'], ['zoom'], 13, 4, 17, 8] as never

export function setJunctionsVisible(m: MlMap, visible: boolean): void {
  for (const id of JUNCTION_LAYERS) {
    if (m.getLayer(id)) m.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none')
  }
}

export function setSelectedJunction(m: MlMap, id: string | null): void {
  if (m.getLayer(JUNCTION_SELECTED)) m.setFilter(JUNCTION_SELECTED, ['==', ['get', 'id'], id ?? ''])
}

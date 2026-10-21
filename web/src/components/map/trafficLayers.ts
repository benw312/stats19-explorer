/**
 * DfT traffic count points (rings sized by AADF) and the roads each count applies to:
 * major links cut from OS Open Roads (solid), minor-road stretches (dashed: indicative) and,
 * where OS roads aren't matched, DfT's straight junction-to-junction line (faint dots).
 *
 * Traffic is one magnitude, so it gets one hue (plum, --traffic). Severity already uses
 * red/orange/blue, so no fourth hue clears the CVD check against all three; traffic is
 * told apart by shape instead (rings and dashed links, never filled dots) and the
 * collision layers are dimmed while traffic is shown.
 */
import type { Map as MlMap } from 'maplibre-gl'

import { trafficTileUrl } from '../../lib/traffic'

export const TRAFFIC_SOURCE = 'traffic'
export const TRAFFIC_POINTS = 'traffic-points'
export const TRAFFIC_SELECTED = 'traffic-selected'
const TRAFFIC_SELECTED_LINK = 'traffic-selected-link'
const LINK_LAYERS = {
  major: 'traffic-links-major',
  minor: 'traffic-links-minor',
  schematic: 'traffic-links-schematic',
} as const
export const TRAFFIC_LAYERS = [
  TRAFFIC_SELECTED_LINK,
  ...Object.values(LINK_LAYERS),
  TRAFFIC_POINTS,
  TRAFFIC_SELECTED,
] as const

const PLUM = '#8a2c99'
const MUTED = '#7a8089'

// Ring radius by AADF (square-root scale so area tracks flow); zoom must stay the outer input.
const sqrtAadf = ['sqrt', ['coalesce', ['get', 'aadf'], 0]]
const ringRadius = (extra: number) =>
  [
    'interpolate',
    ['linear'],
    ['zoom'],
    6,
    ['interpolate', ['linear'], sqrtAadf, 0, 1 + extra, 100, 1.5 + extra, 450, 4 + extra],
    13,
    ['interpolate', ['linear'], sqrtAadf, 0, 3 + extra, 100, 5 + extra, 400, 14 + extra],
  ] as never

const byQuality = (current: unknown, old: unknown, historic: unknown) =>
  ['match', ['get', 'quality'], [0, 1], current, 2, old, historic] as never

export function addTrafficLayers(m: MlMap, visible: boolean): void {
  const visibility = visible ? 'visible' : 'none'
  m.addSource(TRAFFIC_SOURCE, { type: 'vector', tiles: [trafficTileUrl()], minzoom: 4, maxzoom: 14 })
  const width = (scale: number, floor = 1) =>
    [
      'interpolate',
      ['linear'],
      ['coalesce', ['get', 'aadf'], 0],
      0,
      floor,
      20000,
      2.5 * scale,
      100000,
      5 * scale,
    ] as never
  const lineStyles = {
    major: { width: width(1), opacity: byQuality(0.6, 0.4, 0.25), dash: undefined },
    minor: { width: width(0.8, 1.6), opacity: byQuality(0.8, 0.55, 0.35), dash: [3, 1.5] },
    schematic: { width: width(0.6), opacity: byQuality(0.45, 0.3, 0), dash: [0.5, 2] },
  }
  // the open count point's road, as a wide ink casing under the plum line
  m.addLayer({
    id: TRAFFIC_SELECTED_LINK,
    type: 'line',
    source: TRAFFIC_SOURCE,
    'source-layer': 'traffic_links',
    filter: ['==', ['get', 'id'], -1],
    layout: { visibility, 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#1c2126', 'line-opacity': 0.75, 'line-width': width(1, 3.5) },
  })
  for (const [kind, style] of Object.entries(lineStyles) as [
    keyof typeof LINK_LAYERS,
    (typeof lineStyles)['major'],
  ][]) {
    m.addLayer({
      id: LINK_LAYERS[kind],
      type: 'line',
      source: TRAFFIC_SOURCE,
      'source-layer': 'traffic_links',
      filter: ['==', ['get', 'kind'], kind],
      layout: { visibility, 'line-cap': kind === 'major' ? 'round' : 'butt' },
      paint: {
        'line-color': byQuality(PLUM, PLUM, MUTED),
        'line-opacity': style.opacity,
        'line-width': style.width,
        ...(style.dash ? { 'line-dasharray': style.dash } : {}),
      },
    })
  }
  m.addLayer({
    id: TRAFFIC_POINTS,
    type: 'circle',
    source: TRAFFIC_SOURCE,
    'source-layer': 'traffic_points',
    layout: { visibility, 'circle-sort-key': ['-', 0, ['coalesce', ['get', 'aadf'], 0]] as never },
    paint: {
      'circle-radius': ringRadius(0),
      'circle-color': PLUM,
      'circle-opacity': byQuality(0.18, 0, 0),
      'circle-stroke-color': byQuality(PLUM, PLUM, MUTED),
      'circle-stroke-opacity': byQuality(1, 0.6, 0.7),
      'circle-stroke-width': [
        'interpolate',
        ['linear'],
        ['zoom'],
        6,
        byQuality(0.8, 0.6, 0.5),
        11,
        byQuality(2, 1.5, 1),
      ] as never,
    },
  })
  m.addLayer({
    id: TRAFFIC_SELECTED,
    type: 'circle',
    source: TRAFFIC_SOURCE,
    'source-layer': 'traffic_points',
    filter: ['==', ['get', 'id'], -1],
    layout: { visibility },
    paint: {
      'circle-radius': ringRadius(4),
      'circle-color': 'rgba(0,0,0,0)',
      'circle-stroke-color': '#1c2126',
      'circle-stroke-width': 3,
    },
  })
}

export function setTrafficVisible(m: MlMap, visible: boolean): void {
  for (const id of TRAFFIC_LAYERS) {
    if (m.getLayer(id)) m.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none')
  }
}

export function setSelectedCountPoint(m: MlMap, id: number | null): void {
  for (const layer of [TRAFFIC_SELECTED, TRAFFIC_SELECTED_LINK]) {
    if (m.getLayer(layer)) m.setFilter(layer, ['==', ['get', 'id'], id ?? -1])
  }
}

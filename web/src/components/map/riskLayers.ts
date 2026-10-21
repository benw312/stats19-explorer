/**
 * Risk layer (PLAN-008 T4 / FU-038): count point roads and junctions coloured by where their
 * Empirical Bayes excess ranks among similar sites. It answers "where is worse than it
 * should be for its traffic?" without opening the ranked list.
 *
 * Diverging bands from lib/safety (worse = amber to brown, as expected = grey, better =
 * teal), with worse bands drawn wider and larger so colour is never the only cue. The
 * period is fixed (the safety model's last five years), so the layer ignores the filters.
 * Collisions dim while it's shown, as they do for traffic.
 */
import type { ExpressionSpecification, Map as MlMap } from 'maplibre-gl'

import { RISK_BANDS, safetyTileUrl } from '../../lib/safety'

export const RISK_SOURCE = 'risk'
export const RISK_LINKS = 'risk-links'
export const RISK_JUNCTIONS = 'risk-junctions'
const RISK_SELECTED_LINK = 'risk-selected-link'
/** The lowest risk layer, for drawing beneath the whole layer (the route halo). */
export const RISK_FIRST_LAYER = RISK_SELECTED_LINK
const RISK_SELECTED_JUNCTION = 'risk-selected-junction'
const RISK_LAYERS = [RISK_SELECTED_LINK, RISK_LINKS, RISK_JUNCTIONS, RISK_SELECTED_JUNCTION] as const
const INK = '#1c2126'
const ACCENT = '#0a6b45'

const bandColor = [
  'match',
  ['get', 'band'],
  ...RISK_BANDS.flatMap((b) => [b.band, b.color]),
  '#a8a49a',
] as unknown as ExpressionSpecification

// worse bands wider and larger; zoom must stay the outermost input, so selection outlines
// take an offset rather than wrapping these in arithmetic
const lineWidth = (extra = 0) =>
  [
    'interpolate',
    ['linear'],
    ['zoom'],
    6,
    ['match', ['get', 'band'], 3, 3 + extra, 2, 2.4 + extra, 1, 1.8 + extra, 0.8 + extra],
    13,
    ['match', ['get', 'band'], 3, 8 + extra, 2, 6.5 + extra, 1, 5 + extra, 2.5 + extra],
  ] as unknown as ExpressionSpecification

const ringRadius = (extra = 0) =>
  [
    'interpolate',
    ['linear'],
    ['zoom'],
    9,
    ['match', ['get', 'band'], 3, 5 + extra, 2, 4 + extra, 1, 3 + extra, 2 + extra],
    15,
    ['match', ['get', 'band'], 3, 11 + extra, 2, 9 + extra, 1, 7.5 + extra, 5 + extra],
  ] as unknown as ExpressionSpecification

export function addRiskLayers(m: MlMap, visible: boolean, beforeId?: string): void {
  const visibility = visible ? 'visible' : 'none'
  m.addSource(RISK_SOURCE, { type: 'vector', tiles: [safetyTileUrl()], minzoom: 5, maxzoom: 14 })
  // the open road: an ink casing under its band colour
  m.addLayer(
    {
      id: RISK_SELECTED_LINK,
      type: 'line',
      source: RISK_SOURCE,
      'source-layer': 'risk_links',
      filter: ['==', ['get', 'id'], -1],
      layout: { visibility, 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': INK, 'line-opacity': 0.8, 'line-width': lineWidth(5) },
    },
    beforeId,
  )
  m.addLayer(
    {
      id: RISK_LINKS,
      type: 'line',
      source: RISK_SOURCE,
      'source-layer': 'risk_links',
      layout: { visibility, 'line-cap': 'round', 'line-join': 'round', 'line-sort-key': ['get', 'band'] },
      paint: {
        'line-color': bandColor,
        'line-width': lineWidth(),
        'line-opacity': ['match', ['get', 'band'], [0, -1], 0.55, 0.9] as unknown as ExpressionSpecification,
      },
    },
    beforeId,
  )
  m.addLayer(
    {
      id: RISK_JUNCTIONS,
      type: 'circle',
      source: RISK_SOURCE,
      'source-layer': 'risk_junctions',
      layout: { visibility, 'circle-sort-key': ['get', 'band'] },
      paint: {
        'circle-radius': ringRadius(),
        'circle-color': bandColor,
        'circle-opacity': ['match', ['get', 'band'], [0, -1], 0.5, 0.9] as unknown as ExpressionSpecification,
        // a paper ring keeps neighbouring junctions apart where they overlap
        'circle-stroke-color': '#fbfaf7',
        'circle-stroke-width': 1.5,
      },
    },
    beforeId,
  )
  m.addLayer(
    {
      id: RISK_SELECTED_JUNCTION,
      type: 'circle',
      source: RISK_SOURCE,
      'source-layer': 'risk_junctions',
      filter: ['==', ['get', 'id'], ''],
      layout: { visibility },
      paint: {
        'circle-radius': ringRadius(4),
        'circle-color': 'rgba(0,0,0,0)',
        'circle-stroke-color': ACCENT,
        'circle-stroke-width': 3,
      },
    },
    beforeId,
  )
}

export function setRiskSelection(m: MlMap, countPoint: number | null, junction: string | null): void {
  if (m.getLayer(RISK_SELECTED_LINK)) m.setFilter(RISK_SELECTED_LINK, ['==', ['get', 'id'], countPoint ?? -1])
  if (m.getLayer(RISK_SELECTED_JUNCTION)) m.setFilter(RISK_SELECTED_JUNCTION, ['==', ['get', 'id'], junction ?? ''])
}

export function setRiskVisible(m: MlMap, visible: boolean): void {
  for (const id of RISK_LAYERS) {
    if (m.getLayer(id)) m.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none')
  }
}

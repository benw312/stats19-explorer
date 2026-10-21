/**
 * The open route (PLAN-009 V2): a soft accent halo under the risk layer, so the corridor
 * reads as one road while each link keeps its risk colour on top. The link hovered in the
 * strip chart gets an ink outline. Not clickable: clicks fall through to the risk layer.
 */
import type { GeoJSONSource, Map as MlMap } from 'maplibre-gl'

import type { CorridorLink } from '../../lib/routes'

export const ROUTE_SOURCE = 'route'
const ROUTE_HALO = 'route-halo'
const ROUTE_HOVER = 'route-hover'
const ACCENT = '#0a6b45'
const INK = '#1c2126'

export interface RouteCollection {
  type: 'FeatureCollection'
  features: { type: 'Feature'; properties: { id: number }; geometry: CorridorLink['geometry'] }[]
}

export function routeGeoJson(links: readonly CorridorLink[] | null): RouteCollection {
  return {
    type: 'FeatureCollection',
    features: (links ?? []).map((l) => ({
      type: 'Feature',
      properties: { id: l.count_point_id },
      geometry: l.geometry,
    })),
  }
}

export function addRouteLayers(m: MlMap, data: RouteCollection, beforeId?: string): void {
  m.addSource(ROUTE_SOURCE, { type: 'geojson', data })
  m.addLayer(
    {
      id: ROUTE_HALO,
      type: 'line',
      source: ROUTE_SOURCE,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': ACCENT,
        'line-opacity': 0.28,
        'line-width': ['interpolate', ['linear'], ['zoom'], 6, 8, 13, 22],
      },
    },
    beforeId,
  )
  m.addLayer(
    {
      id: ROUTE_HOVER,
      type: 'line',
      source: ROUTE_SOURCE,
      filter: ['==', ['get', 'id'], -1],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': INK,
        'line-opacity': 0.85,
        'line-width': ['interpolate', ['linear'], ['zoom'], 6, 5, 13, 12],
      },
    },
    beforeId,
  )
}

export function setRouteData(m: MlMap, data: RouteCollection): void {
  const source = m.getSource(ROUTE_SOURCE) as GeoJSONSource | undefined
  source?.setData(data)
}

export function setRouteHover(m: MlMap, countPoint: number | null): void {
  if (m.getLayer(ROUTE_HOVER)) m.setFilter(ROUTE_HOVER, ['==', ['get', 'id'], countPoint ?? -1])
}

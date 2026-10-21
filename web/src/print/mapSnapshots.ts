/**
 * One hidden MapLibre map renders every map in a report, one job at a time, and
 * hands back PNG snapshots. Creating a map costs ~1.5 s under software WebGL; moving
 * a live one costs ~0.4 s, so a 25-site pack's maps take a third of the time (FU-018).
 */
import { type GeoJSONSource, Map as MlMap, addProtocol, setWorkerUrl } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { Protocol } from 'pmtiles'

import { addSiteLayers, SITES_SOURCE } from '../components/map/siteLayers'
import { baseStyle } from '../components/map/mapStyle'
import type { Bbox } from '../lib/api'
import { type Site, sitesGeoJson } from '../lib/hotspots'
import { SEVERITIES } from '../lib/severity'

/** Sharper on paper than the 96 dpi screen default. */
const PRINT_PIXEL_RATIO = 2
const PADDING = 30

export interface SnapshotPoint {
  lon: number
  lat: number
  severity: number
}

export interface SnapshotJob {
  width: number
  height: number
  bbox: Bbox
  outline: unknown | null
  points: readonly SnapshotPoint[]
  sites: readonly Site[]
  maxZoom: number
}

const EMPTY: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] }

let ready: Promise<{ map: MlMap; box: HTMLDivElement }> | null = null
let queue: Promise<unknown> = Promise.resolve()

function createMap(): Promise<{ map: MlMap; box: HTMLDivElement }> {
  setWorkerUrl(maplibreWorkerUrl)
  addProtocol('pmtiles', new Protocol().tile)
  const box = document.createElement('div')
  // off-page but laid out (MapLibre needs a real size)
  Object.assign(box.style, { position: 'fixed', left: '-20000px', top: '0', width: '700px', height: '400px' })
  document.body.append(box)
  const map = new MlMap({
    container: box,
    style: baseStyle(window.location.origin),
    interactive: false,
    attributionControl: false,
    canvasContextAttributes: { preserveDrawingBuffer: true },
    pixelRatio: PRINT_PIXEL_RATIO,
    fadeDuration: 0,
  })
  return new Promise((resolve) => {
    map.on('load', () => {
      map.addSource('outline', { type: 'geojson', data: EMPTY })
      map.addLayer({
        id: 'outline-fill',
        type: 'fill',
        source: 'outline',
        paint: { 'fill-color': '#0a6b45', 'fill-opacity': 0.06 },
      })
      map.addLayer({
        id: 'outline-line',
        type: 'line',
        source: 'outline',
        paint: { 'line-color': '#0a6b45', 'line-width': 2 },
      })
      map.addSource('points', { type: 'geojson', data: EMPTY })
      map.addLayer({
        id: 'points',
        type: 'circle',
        source: 'points',
        paint: {
          'circle-color': [
            'match',
            ['get', 'severity'],
            ...SEVERITIES.flatMap((s) => [s.code, s.hex]),
            '#7a8089',
          ] as never,
          'circle-radius': ['match', ['get', 'severity'], 1, 6, 2, 5, 4] as never,
          'circle-stroke-color': ['match', ['get', 'severity'], 1, '#1c2126', '#fbfaf7'] as never,
          'circle-stroke-width': 1.2,
        },
      })
      // printed maps keep every site number (no decluttering)
      addSiteLayers(map, EMPTY, { declutter: false })
      resolve({ map, box })
    })
  })
}

const pointsGeoJson = (points: readonly SnapshotPoint[]): GeoJSON.FeatureCollection => ({
  type: 'FeatureCollection',
  features: [...points]
    .sort((a, b) => b.severity - a.severity) // fatal drawn last (on top)
    .map((p) => ({
      type: 'Feature',
      properties: { severity: p.severity },
      geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
    })),
})

async function render(job: SnapshotJob): Promise<string> {
  ready ??= createMap()
  const { map, box } = await ready
  box.style.width = `${Math.max(1, Math.round(job.width))}px`
  box.style.height = `${Math.round(job.height)}px`
  map.resize()
  const source = (id: string) => map.getSource(id) as GeoJSONSource
  source('outline').setData(
    job.outline
      ? { type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry: job.outline as never }] }
      : EMPTY,
  )
  source('points').setData(pointsGeoJson(job.points))
  source(SITES_SOURCE).setData(sitesGeoJson(job.sites, null, null) as GeoJSON.FeatureCollection)
  const [w, s, e, n] = job.bbox
  map.fitBounds(
    [
      [w, s],
      [e, n],
    ],
    { padding: PADDING, maxZoom: job.maxZoom, duration: 0 },
  )
  await new Promise<void>((resolve) => {
    map.once('idle', () => resolve())
    map.triggerRepaint()
  })
  return map.getCanvas().toDataURL('image/png')
}

/** Queue a map; resolves with a PNG data URL once it is fully drawn. */
export function snapshotMap(job: SnapshotJob): Promise<string> {
  const result = queue.then(() => render(job))
  queue = result.catch(() => undefined)
  return result
}

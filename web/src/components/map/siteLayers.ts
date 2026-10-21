/** Cluster site circles and numbered badges (explorer map and report maps). */
import type { Map as MlMap } from 'maplibre-gl'

export const SITES_SOURCE = 'sites'
export const SITES_FILL = 'sites-fill'
export const SITES_BADGE = 'sites-badge'
export const SITES_BADGE_ACTIVE = 'sites-badge-active'
const ACCENT = '#0a6b45'

const byState = (selected: unknown, hover: unknown, none: unknown) =>
  ['match', ['get', 'state'], 'selected', selected, 'hover', hover, none] as never

/** declutter: hide badges that collide (explorer); off for printed maps, which need every number. */
export function addSiteLayers(m: MlMap, data: GeoJSON.FeatureCollection, { declutter = true } = {}): void {
  m.addSource(SITES_SOURCE, { type: 'geojson', data })
  const circles = ['==', ['get', 'kind'], 'circle'] as never
  const labels = ['==', ['get', 'kind'], 'label'] as never
  m.addLayer({
    id: SITES_FILL,
    type: 'fill',
    source: SITES_SOURCE,
    filter: circles,
    paint: { 'fill-color': ACCENT, 'fill-opacity': byState(0.16, 0.12, 0.06) },
  })
  m.addLayer({
    id: 'sites-line',
    type: 'line',
    source: SITES_SOURCE,
    filter: circles,
    paint: { 'line-color': byState('#1c2126', ACCENT, ACCENT), 'line-width': byState(3, 2.5, 1.5) },
  })
  addBadgeImages(m)
  const badge = (id: string, filter: unknown, allowOverlap: boolean) =>
    m.addLayer({
      id,
      type: 'symbol',
      source: SITES_SOURCE,
      filter: filter as never,
      layout: {
        'icon-image': byState('site-badge-dark', 'site-badge', 'site-badge'),
        'icon-size': byState(1.15, 1.05, 1),
        'text-field': ['to-string', ['get', 'rank']],
        'text-font': ['Noto Sans Medium'],
        'text-size': 11,
        // decluttered: where badges collide, the better-ranked site wins (FU-021)
        'symbol-sort-key': ['get', 'rank'],
        'icon-allow-overlap': allowOverlap,
        'text-allow-overlap': allowOverlap,
        'icon-padding': 1,
      },
      paint: { 'text-color': '#ffffff' },
    })
  const isActive = ['!=', ['get', 'state'], 'none']
  badge(SITES_BADGE, declutter ? ['all', labels, ['==', ['get', 'state'], 'none']] : labels, !declutter)
  // the selected / hovered site's number always shows, on top
  if (declutter) badge(SITES_BADGE_ACTIVE, ['all', labels, isActive], true)
}

const BADGE_PX = 22

/** Round badge images (2x for sharp print), drawn once per map. */
function addBadgeImages(m: MlMap): void {
  for (const [name, fill] of [
    ['site-badge', ACCENT],
    ['site-badge-dark', '#1c2126'],
  ] as const) {
    if (m.hasImage(name)) continue
    const size = BADGE_PX * 2
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = size
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.beginPath()
    ctx.arc(size / 2, size / 2, size / 2 - 3, 0, Math.PI * 2)
    ctx.fillStyle = fill
    ctx.fill()
    ctx.lineWidth = 3
    ctx.strokeStyle = '#fbfaf7'
    ctx.stroke()
    m.addImage(name, ctx.getImageData(0, 0, size, size), { pixelRatio: 2 })
  }
}

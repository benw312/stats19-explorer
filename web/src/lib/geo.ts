import type { Bbox } from './api'
import type { LonLat } from './filter'

const EARTH_RADIUS_M = 6_371_008.8

/** Closed ring approximating a circle (good to well under 1 m at these radii). */
export function circleRing(lon: number, lat: number, radiusM: number, steps = 72): LonLat[] {
  const φ1 = (lat * Math.PI) / 180
  const λ1 = (lon * Math.PI) / 180
  const δ = radiusM / EARTH_RADIUS_M
  const ring: LonLat[] = []
  for (let i = 0; i <= steps; i++) {
    const θ = (2 * Math.PI * i) / steps
    const φ2 = Math.asin(Math.sin(φ1) * Math.cos(δ) + Math.cos(φ1) * Math.sin(δ) * Math.cos(θ))
    const λ2 = λ1 + Math.atan2(Math.sin(θ) * Math.sin(δ) * Math.cos(φ1), Math.cos(δ) - Math.sin(φ1) * Math.sin(φ2))
    ring.push([(λ2 * 180) / Math.PI, (φ2 * 180) / Math.PI])
  }
  ring[ring.length - 1] = ring[0]
  return ring
}

export function ringBbox(ring: readonly LonLat[]): Bbox {
  const xs = ring.map((p) => p[0])
  const ys = ring.map((p) => p[1])
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]
}

/** Haversine distance in metres. */
export function distanceM(a: LonLat, b: LonLat): number {
  const toRad = (d: number) => (d * Math.PI) / 180
  const dφ = toRad(b[1] - a[1])
  const dλ = toRad(b[0] - a[0])
  const h = Math.sin(dφ / 2) ** 2 + Math.cos(toRad(a[1])) * Math.cos(toRad(b[1])) * Math.sin(dλ / 2) ** 2
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h))
}

export interface MapViewState {
  zoom: number
  center: LonLat
}

/** The view MapLibre keeps in the URL hash ("#map=zoom/lat/lon[/bearing/pitch]"). */
export function parseMapHash(hash: string): MapViewState | null {
  const m = /^#map=([\d.]+)\/(-?[\d.]+)\/(-?[\d.]+)/.exec(hash)
  if (!m) return null
  const [zoom, lat, lon] = [Number(m[1]), Number(m[2]), Number(m[3])]
  if (zoom > 24 || Math.abs(lat) > 85 || Math.abs(lon) > 180) return null
  return { zoom, center: [lon, lat] }
}

export function unionBbox(boxes: readonly Bbox[]): Bbox | null {
  if (boxes.length === 0) return null
  return [
    Math.min(...boxes.map((b) => b[0])),
    Math.min(...boxes.map((b) => b[1])),
    Math.max(...boxes.map((b) => b[2])),
    Math.max(...boxes.map((b) => b[3])),
  ]
}

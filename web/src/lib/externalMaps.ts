/**
 * Links out to Google Maps (FU-029) for aerial imagery and Street View. Documented
 * "Maps URLs": no API key, open in a new tab or the Maps app. Nothing is fetched
 * by this app; coordinates reach Google only when the user follows a link.
 */
const GOOGLE = 'https://www.google.com/maps/@'

const point = (lon: number, lat: number): string => `${lat.toFixed(5)},${lon.toFixed(5)}`

/** MapLibre's 512 px tiles put it one zoom level behind Google's 256 px tiles. */
const googleZoom = (mapZoom: number): number => Math.min(21, Math.max(3, Math.round(mapZoom + 1)))

export function googleAerialUrl(lon: number, lat: number, mapZoom: number): string {
  const q = new URLSearchParams({
    api: '1',
    map_action: 'map',
    center: point(lon, lat),
    zoom: String(googleZoom(mapZoom)),
    basemap: 'satellite',
  })
  return `${GOOGLE}?${q.toString()}`
}

export function googleStreetViewUrl(lon: number, lat: number): string {
  const q = new URLSearchParams({ api: '1', map_action: 'pano', viewpoint: point(lon, lat) })
  return `${GOOGLE}?${q.toString()}`
}

/** A site or collision: aerial close in. */
export const SITE_MAP_ZOOM = 17.5

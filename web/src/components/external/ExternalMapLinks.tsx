import { SITE_MAP_ZOOM, googleAerialUrl, googleStreetViewUrl } from '../../lib/externalMaps'
import { parseMapHash } from '../../lib/geo'
import styles from './ExternalMapLinks.module.css'

const NEW_TAB = { target: '_blank', rel: 'noopener noreferrer' } as const

/** Aerial and Street View links for a fixed point (a site or a collision). */
export function ExternalMapLinks({ lon, lat, zoom = SITE_MAP_ZOOM }: { lon: number; lat: number; zoom?: number }) {
  return (
    <span className={styles.links} data-screen-only>
      <span className={styles.label}>Google Maps</span>
      <a className={styles.link} href={googleAerialUrl(lon, lat, zoom)} {...NEW_TAB}>
        Aerial<span aria-hidden> ↗</span>
        <span className="visually-hidden"> (opens Google Maps in a new tab)</span>
      </a>
      <a className={styles.link} href={googleStreetViewUrl(lon, lat)} {...NEW_TAB}>
        Street View<span aria-hidden> ↗</span>
        <span className="visually-hidden"> (opens Google Maps in a new tab)</span>
      </a>
    </span>
  )
}

/** The same for whatever the map is showing now (read from the URL hash on click). */
export function ExternalMapLinksForView() {
  const open = (kind: 'aerial' | 'pano') => {
    const view = parseMapHash(window.location.hash)
    if (!view) return
    const [lon, lat] = view.center
    const url = kind === 'aerial' ? googleAerialUrl(lon, lat, view.zoom) : googleStreetViewUrl(lon, lat)
    window.open(url, '_blank', 'noopener,noreferrer')
  }
  return (
    <span className={styles.links} data-screen-only>
      <span className={styles.label}>Map centre in Google</span>
      <button type="button" className={styles.link} onClick={() => open('aerial')}>
        Aerial<span aria-hidden> ↗</span>
      </button>
      <button type="button" className={styles.link} onClick={() => open('pano')}>
        Street View<span aria-hidden> ↗</span>
      </button>
    </span>
  )
}

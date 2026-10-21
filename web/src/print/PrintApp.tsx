import { AreaReport } from './AreaReport'
import { CollisionReport } from './CollisionReport'
import { RatesReport } from './RatesReport'
import { SitePack } from './SitePack'
import { SiteReport } from './SiteReport'
import './print-pages.css'
import styles from './print.module.css'
import { signalError } from './ready'

/** /print/area, /print/rates, /print/sites, /print/collision/{id}, /print/junction/{id} and /print/road/{id}: PDF pages. */
export function PrintApp() {
  const path = window.location.pathname
  if (path === '/print/area') return <AreaReport />
  if (path === '/print/rates') return <RatesReport />
  if (path === '/print/sites') return <SitePack />
  const m = /^\/print\/collision\/([0-9A-Z]{4,20})$/.exec(path)
  if (m) return <CollisionReport id={m[1]} />
  const site = /^\/print\/(junction|road)\/([0-9A-Za-z_-]{1,64})$/.exec(path)
  if (site) return <SiteReport kind={site[1] as 'junction' | 'road'} id={site[2]} />
  signalError(`unknown print page ${path}`)
  return <p className={styles.loading}>Unknown report.</p>
}

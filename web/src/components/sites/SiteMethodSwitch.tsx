import { SITE_METHODS, type SiteMethod } from '../../lib/siteMethods'
import styles from './sites.module.css'

interface SiteMethodSwitchProps {
  method: SiteMethod
  onMethod: (m: SiteMethod) => void
}

/** The Sites view's two ways of screening the network. */
export function SiteMethodSwitch({ method, onMethod }: SiteMethodSwitchProps) {
  const current = SITE_METHODS.find((m) => m.id === method) ?? SITE_METHODS[0]
  return (
    <div className={styles.switchBlock}>
      <div className={styles.switch} role="group" aria-label="How to find sites">
        {SITE_METHODS.map((m) => (
          <button key={m.id} type="button" aria-pressed={m.id === method} onClick={() => onMethod(m.id)}>
            {m.label}
          </button>
        ))}
      </div>
      <p className={styles.switchNote}>{current.note}</p>
    </div>
  )
}

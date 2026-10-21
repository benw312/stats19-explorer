import { type IndicatorRow, pct } from '../../lib/hotspots'
import styles from './hotspots.module.css'

interface OverRepresentationProps {
  rows: readonly IndicatorRow[]
  siteCollisions: number
  baseCollisions: number
  /** Phrase for the comparison area: "Devon", "the drawn area". */
  baseLabel: string
  /** Inside a titled section (the site page): leave out the heading, keep the key. */
  bare?: boolean
}

const capitalise = (t: string): string => t.charAt(0).toUpperCase() + t.slice(1)

const ratioText = (r: IndicatorRow): string =>
  r.ratio !== null && r.share !== null && r.share > 0 ? ` · ×${r.ratio.toFixed(1)}` : ''

/**
 * Site share (bar) against the area share (tick) for each recorded-field indicator.
 * Rows flagged "notable" are unlikely to be chance (one-sided binomial p < 0.05).
 */
export function OverRepresentation(props: OverRepresentationProps) {
  const { rows, siteCollisions, baseCollisions, baseLabel, bare = false } = props
  const shown = rows.filter((r) => r.of > 0 && r.base_of > 0)
  const notable = shown.filter((r) => r.notable)
  const groups = [...new Set(shown.map((r) => r.group))]

  return (
    <section
      className={styles.over}
      aria-labelledby={bare ? undefined : 'over-h'}
      aria-label={bare ? 'What’s different' : undefined}
    >
      <div className={styles.overHead}>
        {!bare && (
          <h3 id="over-h" className={styles.overTitle}>
            What’s different here
          </h3>
        )}
        <div className={styles.legend} aria-hidden>
          <span>
            <i className={styles.swatchBar} /> Site
          </span>
          <span>
            <i className={styles.swatchTick} /> {capitalise(baseLabel)}
          </span>
          <span>
            <i className={styles.swatchNotable} /> Notable
          </span>
        </div>
      </div>
      <p className={styles.overSub}>
        Share of the site’s {siteCollisions.toLocaleString('en-GB')} collisions compared with{' '}
        {baseCollisions.toLocaleString('en-GB')} in {baseLabel} (same filters). Unknown values are left out. “Notable”
        means unlikely to be chance (p &lt; 0.05); with this many indicators, expect about one by chance per site.
      </p>

      {notable.length > 0 ? (
        <div className={styles.notableBox}>
          <p>
            <strong>Worth a look:</strong>
          </p>
          <ul>
            {notable.map((r) => (
              <li key={r.key}>
                {r.label} — {r.n} of {r.of} ({pct(r.share)}) vs {pct(r.base_share)}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className={styles.overSub}>Nothing stands out from {baseLabel} at this site.</p>
      )}

      <div className={styles.groups}>
        {groups.map((g) => (
          <div key={g} className={styles.groupBlock}>
            <h4 className={styles.group}>{g}</h4>
            {shown
              .filter((r) => r.group === g)
              .map((r) => (
                <div key={r.key} className={styles.row} data-notable={r.notable ? 'yes' : 'no'}>
                  <span className={styles.rowLabel}>
                    {r.label}
                    {r.notable && <span className={styles.flag}>NOTABLE</span>}
                  </span>
                  <span
                    className={styles.track}
                    role="img"
                    aria-label={`Site ${pct(r.share)}, ${baseLabel} ${pct(r.base_share)}`}
                  >
                    <span className={styles.bar} style={{ width: `${(r.share ?? 0) * 100}%` }} />
                    <span className={styles.tick} style={{ left: `${(r.base_share ?? 0) * 100}%` }} />
                  </span>
                  <span className={styles.nums}>
                    <b>
                      {r.n}/{r.of} {pct(r.share)}
                    </b>{' '}
                    vs {pct(r.base_share)}
                    <span className={styles.ratio}>{ratioText(r)}</span>
                  </span>
                </div>
              ))}
          </div>
        ))}
      </div>
    </section>
  )
}

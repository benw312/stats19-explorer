import { RISK_BANDS } from '../../lib/safety'
import { SEVERITIES } from '../../lib/severity'
import { ExternalMapLinksForView } from '../external/ExternalMapLinks'
import styles from './Legend.module.css'

interface LegendProps {
  heatmap: boolean
  onToggleHeatmap: () => void
  traffic: boolean
  onToggleTraffic: () => void
  junctions: boolean
  onToggleJunctions: () => void
  risk: boolean
  onToggleRisk: () => void
  /** False in the Traffic view: no collision key or collision-based layers. */
  collisions?: boolean
}

const DOT_SIZE: Record<number, number> = { 1: 12, 2: 9, 3: 7 }

export function Legend(props: LegendProps) {
  const { heatmap, onToggleHeatmap, traffic, onToggleTraffic, junctions, onToggleJunctions, risk, onToggleRisk } = props
  const collisions = props.collisions ?? true
  return (
    <aside className={styles.legend} aria-label="Map legend">
      {collisions ? <CollisionKey heatmap={heatmap} onToggleHeatmap={onToggleHeatmap} /> : <TrafficKeyHead />}
      <label className={`${styles.toggle} ${collisions ? styles.toggleTight : ''}`}>
        <input type="checkbox" checked={traffic} onChange={onToggleTraffic} className={styles.trafficInput} />
        Traffic count points
      </label>
      {traffic && (
        <p className={styles.trafficKey}>
          <span className={styles.ring} aria-hidden /> Rings sized by daily flow · faded = old count · grey = no longer
          counted. Lines: the road each count covers (dashed = minor road, indicative)
        </p>
      )}
      <label className={`${styles.toggle} ${styles.toggleTight}`}>
        <input type="checkbox" checked={junctions} onChange={onToggleJunctions} />
        Junctions
      </label>
      {junctions && (
        <p className={styles.trafficKey}>
          <span className={styles.junctionRing} aria-hidden /> From street level.{' '}
          {collisions
            ? 'Rings sized by junction collisions matching the filters; click for arms, flows and the rate'
            : 'Click one for its arms and flows'}
        </p>
      )}
      {collisions && <RiskToggle risk={risk} onToggleRisk={onToggleRisk} />}
      <p className={styles.external}>
        <ExternalMapLinksForView />
      </p>
    </aside>
  )
}

function TrafficKeyHead() {
  return (
    <>
      <p className="eyebrow">Traffic</p>
      <p className={styles.note}>DfT flows only: collisions are hidden in this view.</p>
    </>
  )
}

function CollisionKey({ heatmap, onToggleHeatmap }: Pick<LegendProps, 'heatmap' | 'onToggleHeatmap'>) {
  return (
    <>
      <p className="eyebrow">Severity</p>
      <ul className={styles.list}>
        {SEVERITIES.map((s) => (
          <li key={s.code}>
            <span
              className={styles.dot}
              style={{ background: s.cssVar, width: DOT_SIZE[s.code], height: DOT_SIZE[s.code] }}
              aria-hidden
            />
            {s.label}
          </li>
        ))}
      </ul>
      <p className={styles.note}>
        Dark circles are grouped counts — click to zoom in. Individual collisions appear from street level.
      </p>
      <label className={styles.toggle}>
        <input type="checkbox" checked={heatmap} onChange={onToggleHeatmap} />
        Density heat map
      </label>
    </>
  )
}

function RiskToggle({ risk, onToggleRisk }: Pick<LegendProps, 'risk' | 'onToggleRisk'>) {
  return (
    <>
      <label className={`${styles.toggle} ${styles.toggleTight}`}>
        <input type="checkbox" checked={risk} onChange={onToggleRisk} />
        Worse than similar sites
      </label>
      {risk && (
        <>
          <ul className={styles.riskKey} aria-label="Excess collisions against similar sites">
            {RISK_BANDS.map((b) => (
              <li key={b.band}>
                <span className={styles.riskSwatch} data-band={b.band} style={{ background: b.color }} aria-hidden />
                {b.label}
              </li>
            ))}
          </ul>
          <p className={styles.trafficKey}>
            Count point roads and junctions with traffic, ranked among similar sites in their region by excess
            collisions over the last five years (not affected by the filters). Junctions show the worst 5% until street
            level. Click one for the comparison and scheme return
          </p>
        </>
      )}
    </>
  )
}

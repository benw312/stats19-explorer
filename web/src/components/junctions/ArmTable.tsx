import { type JunctionArm, armLabel, compass } from '../../lib/junctions'
import { formatAadf, reliability } from '../../lib/traffic'
import traffic from '../traffic/traffic.module.css'
import styles from './junctions.module.css'

/** A junction's arms: road, direction and DfT flow (click a flow for its count point). */
export function ArmTable({ arms, onCountPoint }: { arms: JunctionArm[]; onCountPoint?: (id: number) => void }) {
  return (
    <table className={styles.arms}>
      <thead>
        <tr>
          <th scope="col">Road</th>
          <th scope="col">Leaves</th>
          <th scope="col" className={styles.num}>
            AADF
          </th>
        </tr>
      </thead>
      <tbody>
        {arms.map((a) => {
          const r =
            a.quality === null
              ? null
              : reliability({
                  quality: a.quality,
                  road_type: a.count_road_type,
                  latest_year: a.latest_year,
                  last_counted_year: a.last_counted_year,
                })
          return (
            <tr key={a.arm}>
              <th scope="row">
                <span className={a.role === 'major' ? styles.major : undefined}>{armLabel(a)}</span>
                {a.role === 'major' && <span className={styles.role}> major</span>}
              </th>
              <td>{compass(a.bearing)}</td>
              <td className={styles.num}>
                {a.count_point_id === null ? (
                  <span className={traffic.muted}>not counted</span>
                ) : !onCountPoint ? (
                  // reports: plain figures (buttons don't print)
                  <span className="mono">{formatAadf(a.latest_aadf)}</span>
                ) : (
                  <button
                    type="button"
                    className={styles.cpLink}
                    onClick={() => onCountPoint(a.count_point_id as number)}
                    title={r ? `${r.label}: ${r.detail}` : undefined}
                  >
                    {r && <span className={traffic.dot} data-tone={r.tone} aria-hidden />}
                    {formatAadf(a.latest_aadf)}
                  </button>
                )}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

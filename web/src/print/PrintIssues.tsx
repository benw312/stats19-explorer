import type { DataIssue } from '../lib/dataIssues'
import { yearsText } from '../lib/dataIssues'
import styles from './print.module.css'

/** DfT documented issues touching a report's collisions, in full (hover doesn't print; FU-049). */
export function PrintIssues({ issues }: { issues: DataIssue[] }) {
  if (issues.length === 0) return null
  return (
    <section className={`${styles.block} ${styles.about}`}>
      <h2 className={styles.h2}>* DfT documented data issues</h2>
      <p className={styles.small}>
        This report’s collisions include police forces and years where DfT has documented a problem with the data. The
        figures use DfT’s published data as it stands.
      </p>
      <ul className={styles.small}>
        {issues.map((i) => (
          <li key={i.id}>
            <strong>{i.title}</strong>
            {i.years?.length ? ` (in this report: ${yearsText(i.years)})` : ''}. DfT: “{i.dft_text}”
          </li>
        ))}
      </ul>
      <p className={styles.small}>
        Source: DfT, road casualty statistics: known data issues (gov.uk). More in the app under About the data.
      </p>
    </section>
  )
}

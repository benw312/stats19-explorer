import { useQuery } from '@tanstack/react-query'

import { getSelectionIssues, issueHref, yearsText } from '../../lib/dataIssues'
import type { ApiFilter } from '../../lib/filter'
import styles from './dataIssues.module.css'

/** "* DfT documented issue" lines for the collisions a filter selects (FU-049). The figures
 * still use DfT's data; this says when they include a force and year DfT has flagged. */
export function DataIssueNote({ filter }: { filter: ApiFilter }) {
  const issues = useQuery({
    queryKey: ['data-issues', JSON.stringify(filter)],
    queryFn: ({ signal }) => getSelectionIssues(filter, signal),
    staleTime: 5 * 60_000,
  })
  const list = issues.data?.issues ?? []
  if (list.length === 0) return null
  return (
    <ul className={styles.notes} aria-label="DfT documented data issues in this selection">
      {list.map((i) => (
        <li key={i.id} className={styles.note}>
          <span className={styles.mark} aria-hidden>
            *
          </span>
          <span className={styles.text} title={i.summary} tabIndex={0}>
            <strong>DfT documented issue:</strong> {i.title}
            {i.years && i.years.length > 0 ? ` (in this selection: ${yearsText(i.years)})` : ''}.
            <span className={styles.summary}> {i.summary}</span>
          </span>{' '}
          <a className={styles.link} href={issueHref(i.id)} target="_blank" rel="noopener">
            Read more
          </a>
        </li>
      ))}
    </ul>
  )
}

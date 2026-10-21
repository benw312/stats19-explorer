import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import {
  type SchemeSummary,
  SITE_TYPE_LABELS,
  formatDate,
  getSchemeOptions,
  getSchemes,
  stageRank,
  statusText,
} from '../../lib/schemes'
import safety from '../safety/safety.module.css'
import site from '../site/site.module.css'
import traffic from '../traffic/traffic.module.css'
import { SchemePage, type SchemePageLinks } from './SchemePage'
import styles from './schemes.module.css'

interface SchemesPanelProps extends SchemePageLinks {
  selected: string | null
  onSelect: (id: string | null) => void
  wide: boolean
  onToggleWide: () => void
  onClose: () => void
}

/** The Schemes view (PLAN-011 §4): the saved schemes, or one scheme's page. */
export function SchemesPanel(props: SchemesPanelProps) {
  const { selected, onSelect, wide, onToggleWide, onClose } = props
  if (selected) {
    return <SchemePage id={selected} onBack={() => onSelect(null)} {...props} />
  }
  return (
    <aside className={traffic.panel} aria-label="Schemes">
      <header className={traffic.head}>
        <div className={traffic.headTop}>
          <p className="eyebrow">Schemes</p>
          <span className={site.headActions}>
            <button type="button" className={site.widthToggle} aria-pressed={wide} onClick={onToggleWide}>
              {wide ? 'Narrow panel' : 'Widen panel'}
            </button>
            <button type="button" className={traffic.close} onClick={onClose} aria-label="Close schemes">
              ×
            </button>
          </span>
        </div>
      </header>
      <div className={traffic.body}>
        <SchemeList onSelect={onSelect} />
      </div>
    </aside>
  )
}

type Sort = 'status' | 'completed' | 'name' | 'measure'
const SORTS: { id: Sort; label: string }[] = [
  { id: 'status', label: 'Status' },
  { id: 'completed', label: 'Completed' },
  { id: 'name', label: 'Name' },
  { id: 'measure', label: 'Measure' },
]

function sortSchemes(rows: readonly SchemeSummary[], sort: Sort, labels: Map<string, string>): SchemeSummary[] {
  const byName = (a: SchemeSummary, b: SchemeSummary) => a.name.localeCompare(b.name, 'en-GB')
  const compare: Record<Sort, (a: SchemeSummary, b: SchemeSummary) => number> = {
    status: (a, b) => stageRank(a.status) - stageRank(b.status) || byName(a, b),
    // most recent first, undated last
    completed: (a, b) => (b.works_end ?? '').localeCompare(a.works_end ?? '') || byName(a, b),
    name: byName,
    measure: (a, b) =>
      (labels.get(a.measure) ?? a.measure).localeCompare(labels.get(b.measure) ?? b.measure, 'en-GB') || byName(a, b),
  }
  return [...rows].sort(compare[sort])
}

function SchemeList({ onSelect }: { onSelect: (id: string) => void }) {
  const [sort, setSort] = useState<Sort>('status')
  const list = useQuery({ queryKey: ['schemes'], queryFn: ({ signal }) => getSchemes(signal) })
  const options = useQuery({
    queryKey: ['scheme-options'],
    queryFn: ({ signal }) => getSchemeOptions(signal),
    staleTime: Infinity,
  })
  const labels = useMemo(() => new Map(options.data?.measures.map((m) => [m.code, m.label])), [options.data])
  const rows = useMemo(() => sortSchemes(list.data ?? [], sort, labels), [list.data, sort, labels])

  return (
    <section className={traffic.section} aria-labelledby="scheme-list">
      <h3 id="scheme-list" className={`${traffic.sectionTitle} ${styles.first}`}>
        Saved schemes
      </h3>
      <p className={traffic.sectionNote}>
        Schemes recorded at a junction, road, cluster site, route or area, with their works dates, so you can see
        whether they worked as the after-data arrives. DfT publishes a year’s data each September.
      </p>
      {list.isError && (
        <p className={traffic.notice} role="alert">
          Couldn’t load the schemes. {list.error instanceof Error ? list.error.message : ''}
        </p>
      )}
      {list.data && list.data.length === 0 && (
        <div className={styles.empty}>
          <p>
            <strong>No schemes yet.</strong>
          </p>
          <p>
            Open a junction or road page, a cluster site, a route, or select an area, then choose{' '}
            <em>Save as scheme</em>. The site’s footprint and its FYRR figures are saved with it.
          </p>
        </div>
      )}
      {rows.length > 0 && (
        <>
          <div className={safety.tabs} role="group" aria-label="Sort schemes by">
            {SORTS.map((s) => (
              <button key={s.id} type="button" aria-pressed={sort === s.id} onClick={() => setSort(s.id)}>
                {s.label}
              </button>
            ))}
          </div>
          <ol className={styles.list}>
            {rows.map((s) => (
              <li key={s.id}>
                <button type="button" className={styles.row} onClick={() => onSelect(s.id)}>
                  <span className={styles.rowName}>{s.name}</span>
                  <span className={styles.rowStatus} data-stage={s.status.stage}>
                    {statusText(s.status)}
                  </span>
                  <span className={styles.rowDetail}>
                    {labels.get(s.measure) ?? s.measure} · {SITE_TYPE_LABELS[s.site_type]}
                    {s.works_end ? ` · completed ${formatDate(s.works_end)}` : ''}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </>
      )}
      {list.isPending && <p className={styles.muted}>Loading…</p>}
    </section>
  )
}

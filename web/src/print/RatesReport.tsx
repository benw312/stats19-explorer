import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo } from 'react'

import { describeFilter, getMeta } from '../lib/api'
import type { ApiFilter } from '../lib/filter'
import { getSelectionIssues } from '../lib/dataIssues'
import { getRates } from '../lib/rates'
import { PrintIssues } from './PrintIssues'
import { RatesSection } from './RatesSection'
import styles from './print.module.css'
import { GENERATED_ON, signalError, signalReady } from './ready'

function parseFilter(raw: string | null): ApiFilter | null {
  try {
    return raw ? (JSON.parse(raw) as ApiFilter) : ({} as ApiFilter)
  } catch {
    return null
  }
}

/** /print/rates: an authority's rates and benchmarking on their own, with no collision cap (V4). */
export function RatesReport() {
  const params = new URLSearchParams(window.location.search)
  const filter = useMemo(() => parseFilter(params.get('f')), []) // eslint-disable-line react-hooks/exhaustive-deps
  const title = params.get('title') || 'Road casualty rates'
  const notes = params.get('notes') ?? ''

  const enabled = filter !== null
  const meta = useQuery({ queryKey: ['meta'], queryFn: ({ signal }) => getMeta(signal), enabled })
  const describe = useQuery({ queryKey: ['d'], queryFn: ({ signal }) => describeFilter(filter!, signal), enabled })
  const rates = useQuery({ queryKey: ['r'], queryFn: ({ signal }) => getRates(filter!, signal), enabled })
  const issues = useQuery({ queryKey: ['i'], queryFn: ({ signal }) => getSelectionIssues(filter!, signal), enabled })
  const failed = [meta, describe, rates, issues].find((q) => q.isError)
  const loaded = [meta, describe, rates, issues].every((q) => q.isSuccess)

  useEffect(() => {
    if (filter === null) signalError('invalid filter')
    else if (failed) signalError(failed.error instanceof Error ? failed.error.message : 'data request failed')
    else if (loaded) void signalReady()
  }, [filter, failed, loaded])

  if (!loaded) return <p className={styles.loading}>Preparing report…</p>
  const run = meta.data!.last_run
  return (
    <article className={styles.report}>
      <header className={styles.cover}>
        <p className={styles.eyebrow}>STATS19 road casualty rates</p>
        <h1 className={styles.title}>{title}</h1>
        <p className={styles.metaLine}>
          Generated {GENERATED_ON} · DfT STATS19 {meta.data!.coverage.first_year}–{meta.data!.coverage.last_year}
          {run ? ` · data load ${run.run_id}` : ''}
        </p>
      </header>
      <section className={styles.selection}>
        <h2 className={styles.h2}>Selection</h2>
        <ul>
          {describe.data!.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        {notes && (
          <div className={styles.notes}>
            <h3>Notes</h3>
            <p>{notes}</p>
          </div>
        )}
      </section>
      <RatesSection d={rates.data!} newPage={false} />
      <PrintIssues issues={issues.data!.issues} />
      <p className={styles.small}>
        Contains public sector information licensed under the Open Government Licence v3.0 (Department for Transport,
        Office for National Statistics).
      </p>
    </article>
  )
}

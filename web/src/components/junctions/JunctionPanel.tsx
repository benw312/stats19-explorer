import { keepPreviousData, useQuery } from '@tanstack/react-query'

import type { ApiFilter } from '../../lib/filter'
import { type Junction, controlLabel, coverageNote, formatRate, getJunction, junctionTitle } from '../../lib/junctions'
import { SEVERITIES } from '../../lib/severity'
import { formatAadf } from '../../lib/traffic'
import { YearColumns } from '../charts/YearColumns'
import { SafetyCompare } from '../safety/SafetyCompare'
import traffic from '../traffic/traffic.module.css'
import { ArmTable } from './ArmTable'
import styles from './junctions.module.css'

interface JunctionPanelProps {
  id: string
  filter: ApiFilter
  onCountPoint: (id: number) => void
  onZoom: (lonLat: [number, number]) => void
  onClose: () => void
  /** Traffic view: arms and flows only, without collisions and the comparison. */
  trafficOnly?: boolean
}

/** One junction: its arms and their DfT flows, collisions here, and the rate per vehicle entering. */
export function JunctionPanel({ id, filter, onCountPoint, onZoom, onClose, trafficOnly = false }: JunctionPanelProps) {
  const junction = useQuery({
    queryKey: ['junction', id, JSON.stringify(filter)],
    queryFn: ({ signal }) => getJunction(id, filter, signal),
    placeholderData: keepPreviousData,
  })

  return (
    <aside className={traffic.panel} aria-label="Junction">
      <header className={traffic.head}>
        <div className={traffic.headTop}>
          <p className="eyebrow">Junction</p>
          <button type="button" className={traffic.close} onClick={onClose} aria-label="Close junction">
            ×
          </button>
        </div>
      </header>
      <div
        className={`${traffic.body} ${junction.isPlaceholderData ? traffic.stale : ''}`}
        aria-busy={junction.isFetching}
      >
        {junction.isError && (
          <p className={traffic.notice} role="alert">
            Couldn’t load this junction. {junction.error instanceof Error ? junction.error.message : ''}
          </p>
        )}
        {junction.data && (
          <JunctionBody j={junction.data} onCountPoint={onCountPoint} onZoom={onZoom} trafficOnly={trafficOnly} />
        )}
      </div>
    </aside>
  )
}

interface BodyProps {
  j: Junction
  onCountPoint: JunctionPanelProps['onCountPoint']
  onZoom: JunctionPanelProps['onZoom']
  trafficOnly: boolean
}

function JunctionBody({ j, onCountPoint, onZoom, trafficOnly }: BodyProps) {
  const control = controlLabel(j)
  const c = trafficOnly ? null : j.collisions
  return (
    <article className={traffic.card}>
      <header className={traffic.pointHead}>
        <p className="eyebrow">
          {j.kind_label} · {j.arms} arms
        </p>
        <h2 className={traffic.pointTitle}>{junctionTitle(j)}</h2>
        <p className={styles.chips}>
          {control && <span className={styles.chip}>{control}</span>}
          {j.nodes > 1 && <span className={styles.chip}>{j.nodes} OS nodes</span>}
        </p>
      </header>

      {c && (
        <section className={styles.hero} aria-label="Collisions at this junction">
          <p className={styles.heroValue}>
            {c.total.toLocaleString('en-GB')}
            <span className={styles.heroUnit}> junction collision{c.total === 1 ? '' : 's'}</span>
          </p>
          <p className={styles.heroCaption}>
            {c.year_from === c.year_to ? c.year_from : `${c.year_from}–${c.year_to}`} · recorded at a junction, within{' '}
            {j.matching.radius_m} m · current filters apply
          </p>
          <ul className={styles.severities}>
            {SEVERITIES.map((s) => (
              <li key={s.code}>
                <span className={styles.sevDot} style={{ background: s.cssVar }} aria-hidden />
                {s.label} <span className="mono">{c[s.label.toLowerCase() as 'fatal' | 'serious' | 'slight']}</span>
              </li>
            ))}
          </ul>
          <Rate j={j} />
        </section>
      )}

      <section className={traffic.section} aria-labelledby="junction-arms">
        <h3 id="junction-arms" className={traffic.sectionTitle}>
          Arms and traffic
        </h3>
        <p className={traffic.sectionNote}>
          {j.flow.entering > 0
            ? `About ${formatAadf(j.flow.entering)} vehicles a day enter (${j.flow.year} AADF: half of each counted arm’s two-way flow). `
            : ''}
          {coverageNote(j.flow)}
        </p>
        <ArmTable arms={j.arm_list} onCountPoint={onCountPoint} />
      </section>

      {!trafficOnly && j.safety && <SafetyCompare unit="junction" s={j.safety} />}

      {c && c.total > 0 && <YearColumns data={c.by_year} />}

      {c && c.total > 0 && <RecordedControl j={j} />}

      <div className={traffic.actions}>
        <button type="button" className={traffic.action} onClick={() => onZoom([j.lon, j.lat])}>
          Zoom to junction
        </button>
      </div>

      <p className={traffic.footnote}>
        Junctions are assembled from OS Open Roads: a roundabout’s ring, or the nodes of one junction (a dual
        carriageway or staggered junction is several), with arms grouped by road and direction.{' '}
        {trafficOnly
          ? ''
          : `Collisions count when STATS19 records them at a junction and they lie within ${j.matching.radius_m} m of it (the last ${j.matching.years} years). `}
        Signals come from OpenStreetMap: signals on the junction, or on two or more approaches. Merges and diverges on
        motorways and dual carriageways stay with the road, as in DfT’s COBALT.
      </p>
    </article>
  )
}

export function Rate({ j }: { j: Junction }) {
  if (!j.rate) {
    return (
      <p className={styles.rateNone}>
        No rate: {j.flow.coverage === 'partial' ? 'a major arm has no DfT count.' : 'no counted traffic here.'}
      </p>
    )
  }
  return (
    <div className={styles.rate}>
      <p className={styles.rateValue}>
        {formatRate(j.rate.per_mve)}
        <span className={styles.heroUnit}> per million vehicles entering</span>
      </p>
      <p className={styles.heroCaption}>
        {j.rate.mve.toLocaleString('en-GB')} million vehicles entered over the period
        {j.rate.coverage === 'major' ? ' (major road only: minor arms uncounted, so the rate reads high)' : ''}.
      </p>
    </div>
  )
}

const CONTROL_WORDS: Record<string, string> = {
  signals: 'traffic signals',
  give_way: 'give way or uncontrolled',
  stop: 'stop sign',
  authorised_person: 'authorised person',
}

export function RecordedControl({ j }: { j: Junction }) {
  const recorded = Object.entries(j.collisions?.recorded_control ?? {}).filter(([, n]) => n > 0)
  if (recorded.length === 0) return null
  return (
    <p className={traffic.footnote}>
      <span className="eyebrow">Police recorded control</span>{' '}
      {recorded.map(([k, n]) => `${CONTROL_WORDS[k] ?? k} ${n}`).join(' · ')}
    </p>
  )
}

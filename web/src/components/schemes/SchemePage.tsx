import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'

import { formatFyrr, formatMoney, formatPayback, fyrr } from '../../lib/economics'
import {
  type Scheme,
  SITE_TYPE_LABELS,
  countedText,
  deleteScheme,
  footprintBbox,
  formatDate,
  getScheme,
  getSchemeCollisions,
  getSchemeOptions,
  saveErrorMessage,
  statusText,
  yearPhase,
} from '../../lib/schemes'
import type { SiteFigure } from '../../lib/site'
import { type ColumnPhase, YearColumns } from '../charts/YearColumns'
import { ExternalMapLinks } from '../external/ExternalMapLinks'
import hotspots from '../hotspots/hotspots.module.css'
import { type SiteSection, SitePage, SiteShell } from '../site/SitePage'
import site from '../site/site.module.css'
import traffic from '../traffic/traffic.module.css'
import { SchemeForm } from './SchemeForm'
import styles from './schemes.module.css'

/** Where a scheme's page links to: its site today, and the map. */
export interface SchemePageLinks {
  onJunction: (id: string) => void
  onCountPoint: (id: number) => void
  onZoomBbox: (bbox: [number, number, number, number]) => void
}

interface SchemePageProps extends SchemePageLinks {
  id: string
  wide: boolean
  onToggleWide: () => void
  onBack: () => void
  onClose: () => void
}

/** One saved scheme (PLAN-011 §4): details, collisions by year, expected return. */
export function SchemePage(props: SchemePageProps) {
  const { id, wide, onToggleWide, onClose, onBack, onZoomBbox } = props
  const scheme = useQuery({ queryKey: ['scheme', id], queryFn: ({ signal }) => getScheme(id, signal) })

  // Show the footprint once, when the scheme opens.
  const zoomed = useRef<string | null>(null)
  useEffect(() => {
    if (scheme.data && zoomed.current !== scheme.data.id) {
      zoomed.current = scheme.data.id
      onZoomBbox(footprintBbox(scheme.data.geometry))
    }
  }, [scheme.data, onZoomBbox])

  return (
    <SiteShell eyebrow="Scheme" wide={wide} onToggleWide={onToggleWide} onClose={onClose} busy={scheme.isFetching}>
      {scheme.isError && (
        <>
          <button type="button" className={hotspots.back} onClick={onBack}>
            ← All schemes
          </button>
          <p className={traffic.notice} role="alert">
            Couldn’t load this scheme. {scheme.error instanceof Error ? scheme.error.message : ''}
          </p>
        </>
      )}
      {scheme.data && <SchemeView {...props} s={scheme.data} />}
    </SiteShell>
  )
}

function SchemeView(props: SchemePageProps & { s: Scheme }) {
  const { s, wide, onBack, onJunction, onCountPoint, onZoomBbox } = props
  const [editing, setEditing] = useState(false)
  const options = useQuery({
    queryKey: ['scheme-options'],
    queryFn: ({ signal }) => getSchemeOptions(signal),
    staleTime: Infinity,
  })
  const collisions = useQuery({
    queryKey: ['scheme-collisions', s.id],
    queryFn: ({ signal }) => getSchemeCollisions(s.id, signal),
  })
  const measure = options.data?.measures.find((m) => m.code === s.measure)?.label ?? s.measure
  const expected = s.fyrr && s.cost ? fyrr({ ...camel(s.fyrr), cost: s.cost }) : null

  const figures: SiteFigure[] = [
    {
      label: 'Completed',
      value: formatDate(s.works_end),
      note: s.works_start ? `started ${formatDate(s.works_start)}` : undefined,
    },
    {
      label: 'Status',
      value:
        s.status.stage === 'monitoring' || s.status.stage === 'complete'
          ? `${s.status.after_months}/${s.status.after_months_wanted}`
          : '–',
      note: statusText(s.status),
    },
    { label: 'Cost', value: s.cost === null ? '–' : formatMoney(s.cost) },
    {
      label: 'Expected FYRR',
      value: expected ? formatFyrr(expected.fyrrPct) : '–',
      note: s.fyrr ? `${s.fyrr.reduction_pct}% fewer collisions` : 'No FYRR saved',
    },
  ]

  const phases = useMemo(() => {
    const d = collisions.data
    if (!d || (!d.before && !d.after)) return undefined
    return Object.fromEntries(d.by_year.map((y) => [y.year, yearPhase(y.year, d.before, d.after) as ColumnPhase]))
  }, [collisions.data])

  const sections: SiteSection[] = [
    {
      id: 'year',
      label: 'Trend',
      content: (
        <>
          {collisions.isError && (
            <p className={traffic.notice} role="alert">
              Couldn’t count the collisions. {collisions.error instanceof Error ? collisions.error.message : ''}
            </p>
          )}
          {collisions.data &&
            (collisions.data.by_year.length > 0 ? (
              <YearColumns
                data={collisions.data.by_year}
                phases={phases}
                subtitle={countedText(collisions.data.match)}
              />
            ) : (
              <p className={site.muted}>No collision data is loaded yet.</p>
            ))}
          <PeriodsNote s={s} before={collisions.data?.before ?? null} after={collisions.data?.after ?? null} />
          <p className={traffic.footnote}>
            The before-and-after evaluation, corrected for the general trend and for regression to the mean (Empirical
            Bayes), is still to come. Until then this chart is descriptive only: a fall after a bad year is partly what
            you’d expect anyway.
          </p>
        </>
      ),
    },
    {
      id: 'details',
      label: 'Details',
      content: (
        <>
          <dl className={styles.details}>
            <dt>Measure</dt>
            <dd>{measure}</dd>
            <dt>Site</dt>
            <dd>{SITE_TYPE_LABELS[s.site_type]}</dd>
            <dt>Works</dt>
            <dd>{worksText(s.works_start, s.works_end)}</dd>
            <dt>Periods</dt>
            <dd>
              {s.before_years} {s.before_years === 1 ? 'year' : 'years'} before, {s.after_years}{' '}
              {s.after_years === 1 ? 'year' : 'years'} after
            </dd>
            <dt>Cost</dt>
            <dd>{s.cost === null ? '–' : `£${s.cost.toLocaleString('en-GB')}`}</dd>
            {s.description && (
              <>
                <dt>Description</dt>
                <dd className={styles.description}>{s.description}</dd>
              </>
            )}
            <dt>Saved</dt>
            <dd>
              {stamp(s.created_at)} by {s.created_by}
              {s.version > 1 ? `; last edited ${stamp(s.updated_at)} by ${s.updated_by}` : ''}
            </dd>
          </dl>
          <div className={site.actions}>
            <button type="button" className={traffic.action} onClick={() => setEditing(true)}>
              Edit
            </button>
            <DeleteScheme s={s} onDeleted={onBack} />
          </div>
        </>
      ),
    },
    {
      id: 'fyrr',
      label: 'Expected return',
      short: 'FYRR',
      content: <ExpectedReturn s={s} />,
    },
    {
      id: 'actions',
      label: 'Site and links',
      short: 'Links',
      content: (
        <>
          <div className={site.actions}>
            {s.site_type === 'junction' && s.site_ref && (
              <button type="button" className={traffic.action} onClick={() => onJunction(s.site_ref ?? '')}>
                Open the junction
              </button>
            )}
            {s.site_type === 'link' && s.site_ref && /^\d+$/.test(s.site_ref) && (
              <button type="button" className={traffic.action} onClick={() => onCountPoint(Number(s.site_ref))}>
                Open the road
              </button>
            )}
            <button type="button" className={traffic.action} onClick={() => onZoomBbox(footprintBbox(s.geometry))}>
              Zoom to footprint
            </button>
          </div>
          <p>
            <ExternalMapLinks lon={s.point[0]} lat={s.point[1]} />
          </p>
          <p className={traffic.footnote}>
            The footprint was saved with the scheme, so its collisions don’t move when junctions, roads or cluster sites
            are rebuilt from new data. The site’s page shows it as it is today.
          </p>
        </>
      ),
    },
  ]

  return (
    <>
      <SitePage
        before={
          <button type="button" className={hotspots.back} onClick={onBack}>
            ← All schemes
          </button>
        }
        kicker={`${measure} · ${SITE_TYPE_LABELS[s.site_type]}`}
        title={s.name}
        subtitle={statusText(s.status)}
        figures={figures}
        sections={sections}
        wide={wide}
      />
      {editing && <SchemeForm mode={{ kind: 'edit', scheme: s }} onClose={() => setEditing(false)} />}
    </>
  )
}

function PeriodsNote({ s, before, after }: { s: Scheme; before: Period | null; after: Period | null }) {
  if (!before) {
    return <p className={traffic.sectionNote}>Add the works dates to mark the before and after periods.</p>
  }
  return (
    <p className={traffic.sectionNote}>
      Before: {formatDate(before.start)} to {formatDate(before.end)}.{' '}
      {after
        ? `After: ${formatDate(after.start)} to ${formatDate(after.end)}; ${statusText(s.status).toLowerCase()}${
            s.status.data_end ? ` (data to ${formatDate(s.status.data_end)})` : ''
          }.`
        : 'The after period starts the day after the works are completed.'}
    </p>
  )
}

type Period = { start: string; end: string }

function ExpectedReturn({ s }: { s: Scheme }) {
  const f = s.fyrr
  if (!f) {
    return (
      <p className={site.muted}>
        No FYRR was saved with this scheme. Saving from a junction or road page carries its Empirical Bayes estimate
        across; edit the scheme to add the cost and expected reduction.
      </p>
    )
  }
  const result = s.cost ? fyrr({ ...camel(f), cost: s.cost }) : null
  return (
    <>
      <dl className={styles.details}>
        <dt>Collisions a year</dt>
        <dd>{f.collisions_per_year.toFixed(2)}</dd>
        <dt>Value each</dt>
        <dd>
          {formatMoney(f.value_per_collision)}
          {f.prices_year ? ` (${f.prices_year} prices)` : ''}
        </dd>
        <dt>Expected reduction</dt>
        <dd>{f.reduction_pct}%</dd>
        {result && (
          <>
            <dt>Saved a year</dt>
            <dd>
              {result.collisionsSaved.toFixed(2)} collisions, {formatMoney(result.valueSaved)}
            </dd>
            <dt>First-year return</dt>
            <dd>
              <strong>{formatFyrr(result.fyrrPct)}</strong>, paying back in {formatPayback(result.paybackYears)}
            </dd>
          </>
        )}
      </dl>
      <p className={traffic.footnote}>
        {f.basis ? `Basis: ${f.basis}. ` : ''}
        {result ? '' : 'Add the cost to see the expected return. '}
        The achieved return, from the evaluation, will sit beside this once it’s built.
      </p>
    </>
  )
}

function DeleteScheme({ s, onDeleted }: { s: Scheme; onDeleted: () => void }) {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (!confirming) {
    return (
      <button type="button" className={`${traffic.action} ${styles.danger}`} onClick={() => setConfirming(true)}>
        Delete
      </button>
    )
  }
  const remove = async () => {
    setBusy(true)
    setError(null)
    try {
      await deleteScheme(s.id)
      queryClient.removeQueries({ queryKey: ['scheme', s.id] })
      await queryClient.invalidateQueries({ queryKey: ['schemes'] })
      onDeleted()
    } catch (e: unknown) {
      setError(saveErrorMessage(e))
      setBusy(false)
    }
  }
  return (
    <div className={styles.confirm} role="group" aria-label="Confirm delete">
      <span>Delete “{s.name}”?</span>
      <button type="button" className={traffic.action} onClick={() => setConfirming(false)} disabled={busy}>
        Keep it
      </button>
      <button
        type="button"
        className={`${traffic.action} ${styles.danger}`}
        onClick={() => void remove()}
        disabled={busy}
      >
        {busy ? 'Deleting…' : 'Delete'}
      </button>
      {error && (
        <p className={traffic.notice} role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

function camel(f: NonNullable<Scheme['fyrr']>) {
  return {
    collisionsPerYear: f.collisions_per_year,
    valuePerCollision: f.value_per_collision,
    reductionPct: f.reduction_pct,
  }
}

function worksText(start: string | null, end: string | null): string {
  if (start && end) return `${formatDate(start)} to ${formatDate(end)}`
  if (end) return `Completed ${formatDate(end)}`
  if (start) return `Started ${formatDate(start)}, not yet completed`
  return 'No dates yet'
}

function stamp(iso: string): string {
  return formatDate(iso.slice(0, 10))
}

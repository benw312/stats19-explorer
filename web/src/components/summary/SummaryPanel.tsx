import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import {
  ApiRequestError,
  type CodeCount,
  type Meta,
  type AreaReportSections,
  areaReportUrl,
  describeFilter,
  exportUrl,
  getSummary,
} from '../../lib/api'
import type { ApiFilter } from '../../lib/filter'
import { sharePct } from '../../lib/format'
import { fillYears } from '../../lib/hotspots'
import { roadUserLabel } from '../../lib/roadUsers'
import type { SchemeDraft } from '../../lib/schemes'
import { HBars } from '../charts/HBars'
import { DataIssueNote } from '../dataIssues/DataIssueNote'
import { TimeMatrix } from '../charts/TimeMatrix'
import { YearColumns } from '../charts/YearColumns'
import { CollisionList } from './CollisionList'
import { RatesTab } from './RatesTab'
import { SaveScheme } from '../schemes/SaveScheme'
import { ReportDialog } from './ReportDialog'
import { SticksTab } from './SticksTab'
import styles from './SummaryPanel.module.css'

interface SummaryPanelProps {
  meta: Meta
  filter: ApiFilter
  wide: boolean
  onToggleWide: () => void
  onOpenCollision: (id: string, lonLat: [number, number] | null) => void
  /** Switch the area to another highway authority (from the Rates tab's similar authorities). */
  onPickAuthority: (code: string) => void
  /** The selected area as a scheme; null without an area. */
  schemeDraft?: SchemeDraft | null
  onOpenScheme?: (id: string) => void
  onClose: () => void
}

type Tab = 'summary' | 'collisions' | 'sticks' | 'rates'

const MAX_REPORT_COLLISIONS = 1000
const LONG_REPORT = 200 // collisions; beyond this sticks + list exceed ~15 pages

const BREAKDOWNS: [string, string][] = [
  ['light_conditions', 'Light conditions'],
  ['road_surface_conditions', 'Road surface'],
  ['weather_conditions', 'Weather'],
  ['speed_limit', 'Speed limit'],
  ['junction_detail', 'Junction detail'],
  ['road_type', 'Road type'],
]

function codeBars(rows: CodeCount[], field: string) {
  return rows.map((r) => ({
    key: String(r.code),
    label: r.label ?? (field === 'speed_limit' ? `${r.code} mph` : String(r.code)),
    n: r.n,
  }))
}

export function SummaryPanel({
  meta,
  filter,
  wide,
  onToggleWide,
  onOpenCollision,
  onPickAuthority,
  schemeDraft = null,
  onOpenScheme,
  onClose,
}: SummaryPanelProps) {
  const [tab, setTab] = useState<Tab>('summary')
  const [reporting, setReporting] = useState(false)
  const [sections, setSections] = useState<AreaReportSections>({ sticks: true, list: true })
  const key = JSON.stringify(filter)
  const summary = useQuery({
    queryKey: ['summary', key],
    queryFn: ({ signal }) => getSummary(filter, signal),
    placeholderData: keepPreviousData,
    retry: (count, error) => !(error instanceof ApiRequestError && error.code === 'too_large') && count < 1,
  })
  const description = useQuery({
    queryKey: ['describe', key],
    queryFn: ({ signal }) => describeFilter(filter, signal),
    placeholderData: keepPreviousData,
  })
  const dayLabels = Object.fromEntries(
    (meta.fields.find((f) => f.table_name === 'collision' && f.field_name === 'day_of_week')?.codes ?? []).map((c) => [
      c.code,
      c.label,
    ]),
  )
  const tooLarge = summary.error instanceof ApiRequestError && summary.error.code === 'too_large'
  const t = summary.data?.totals

  return (
    <aside className={styles.panel} aria-label="Selection summary">
      <header className={styles.head}>
        <div className={styles.headTop}>
          <p className="eyebrow">Selection</p>
          <span>
            <button type="button" className={styles.textButton} aria-pressed={wide} onClick={onToggleWide}>
              {wide ? 'Narrow panel' : 'Widen panel'}
            </button>
            <button type="button" className={styles.close} onClick={onClose} aria-label="Close summary">
              ×
            </button>
          </span>
        </div>
        <ul className={styles.description} aria-live="polite">
          {(description.data ?? []).map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        <DataIssueNote filter={filter} />
        <div className={styles.actions}>
          <ExportLink
            href={exportUrl(filter, 'zip')}
            label="Download CSV"
            limit={meta.limits.export_csv}
            count={t?.collisions}
            blocked={tooLarge}
          />
          <ExportLink
            href={exportUrl(filter, 'xlsx')}
            label="Excel"
            limit={meta.limits.export_xlsx}
            count={t?.collisions}
            blocked={tooLarge}
          />
          <button
            type="button"
            className={styles.export}
            disabled={tooLarge || !t || t.collisions > MAX_REPORT_COLLISIONS}
            title={
              t && t.collisions > MAX_REPORT_COLLISIONS
                ? `Reports cover up to ${MAX_REPORT_COLLISIONS.toLocaleString('en-GB')} collisions`
                : undefined
            }
            onClick={() => setReporting(true)}
          >
            PDF report
          </button>
          {schemeDraft && <SaveScheme draft={schemeDraft} onOpenScheme={onOpenScheme} className={styles.export} />}
        </div>
        <div className={styles.tabs} role="tablist">
          {(['summary', 'collisions', 'sticks', 'rates'] as const).map((id) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              className={styles.tab}
              onClick={() => setTab(id)}
            >
              {id === 'summary'
                ? 'Summary'
                : id === 'sticks'
                  ? 'Stick diagram'
                  : id === 'rates'
                    ? 'Rates'
                    : `Collisions${t ? ` (${t.collisions.toLocaleString('en-GB')})` : ''}`}
            </button>
          ))}
        </div>
      </header>

      <div className={styles.body} aria-busy={summary.isFetching}>
        {tooLarge && (
          <p className={styles.notice} role="status">
            {summary.error instanceof Error ? summary.error.message : ''} Draw an area or pick an authority in{' '}
            <strong>01 Area</strong>.
          </p>
        )}
        {summary.isError && !tooLarge && (
          <p className={styles.notice} role="alert">
            Couldn’t summarise this selection. {summary.error instanceof Error ? summary.error.message : ''}
          </p>
        )}

        {tab === 'summary' && summary.data && t && (
          <div className={summary.isPlaceholderData ? styles.stale : undefined}>
            <dl className={styles.tiles}>
              <Tile label="Collisions" value={t.collisions} lead />
              <Tile
                label="KSI collisions"
                value={t.ksi}
                of={t.collisions}
                note={`${t.ksi_adjusted.toLocaleString('en-GB')} on DfT’s adjusted severity`}
              />
              <Tile
                label="Casualties"
                value={t.casualties}
                note={filter.involves?.length ? 'Everyone hurt in these collisions' : undefined}
              />
              <Tile label="Fatal" value={t.fatal} dot="var(--sev-fatal)" of={t.collisions} />
              <Tile label="Serious" value={t.serious} dot="var(--sev-serious)" of={t.collisions} />
              <Tile label="Slight" value={t.slight} dot="var(--sev-slight)" of={t.collisions} />
            </dl>
            {t.collisions === 0 ? (
              <p className={styles.notice}>No collisions match this selection.</p>
            ) : (
              <>
                <YearColumns data={fillYears(summary.data.by_year, filter.year_from, filter.year_to)} />
                <TimeMatrix data={summary.data.by_dow_hour} dayLabels={dayLabels} />
                <HBars
                  title="Casualties by road user"
                  data={summary.data.casualties_by_group.map((g) => ({
                    key: g.group,
                    label: roadUserLabel(g.group),
                    n: g.total,
                  }))}
                  limit={8}
                />
                {BREAKDOWNS.map(([field, title]) => (
                  <HBars key={field} title={title} data={codeBars(summary.data.breakdowns[field] ?? [], field)} />
                ))}
                <HBars
                  title="Casualty age band"
                  data={summary.data.casualties_by_age_band.map((a) => ({
                    key: String(a.code),
                    label: a.label ?? String(a.code),
                    n: a.n,
                  }))}
                  limit={12}
                />
              </>
            )}
          </div>
        )}

        {tab === 'collisions' && <CollisionList filter={filter} onOpen={onOpenCollision} />}
        {tab === 'rates' && <RatesTab filter={filter} onPickAuthority={onPickAuthority} />}
        {tab === 'sticks' && (
          <SticksTab
            filter={filter}
            collisions={t?.collisions}
            onOpen={(st) =>
              onOpenCollision(st.collision_index, st.lon !== null && st.lat !== null ? [st.lon, st.lat] : null)
            }
          />
        )}
      </div>
      {reporting && (
        <ReportDialog
          heading="PDF area report"
          blurb="Map, summary charts, stick diagram and collision list for the current selection."
          url={(title, notes) => areaReportUrl(filter, title, notes, sections)}
          fallbackName="stats19-area-report.pdf"
          defaultTitle={
            (description.data ?? []).find((l) => l.startsWith('Area:'))?.replace(/^Area:\s*/, '') ?? 'Collision study'
          }
          onClose={() => setReporting(false)}
        >
          <fieldset className={styles.sections}>
            <legend>Include</legend>
            <label>
              <input type="checkbox" checked disabled /> Map, figures and summary charts
            </label>
            <label>
              <input
                type="checkbox"
                checked={sections.sticks}
                onChange={(e) => setSections({ ...sections, sticks: e.target.checked })}
              />{' '}
              Stick diagram
            </label>
            <label>
              <input
                type="checkbox"
                checked={sections.list}
                onChange={(e) => setSections({ ...sections, list: e.target.checked })}
              />{' '}
              Collision list
            </label>
            {t && t.collisions > LONG_REPORT && (
              <p className={styles.hint}>
                {t.collisions.toLocaleString('en-GB')} collisions: the stick diagram and list run to many pages. For
                problem locations, the cluster site pack is usually more useful.
              </p>
            )}
          </fieldset>
        </ReportDialog>
      )}
    </aside>
  )
}

function ExportLink(props: { href: string; label: string; limit: number; count?: number; blocked: boolean }) {
  const over = props.blocked || (props.count !== undefined && props.count > props.limit)
  const why = `Up to ${props.limit.toLocaleString('en-GB')} collisions — narrow the selection`
  return (
    <a
      className={styles.export}
      href={over ? undefined : props.href}
      download={over ? undefined : true}
      aria-disabled={over}
      title={over ? why : undefined}
    >
      {props.label}
    </a>
  )
}

interface TileProps {
  label: string
  value: number
  lead?: boolean
  dot?: string
  /** Show value as a share of this total (top right). */
  of?: number
  /** A short line under the figure. */
  note?: string
}

function Tile({ label, value, lead = false, dot, of, note }: TileProps) {
  return (
    <div className={lead ? `${styles.tile} ${styles.lead}` : styles.tile}>
      <dt>
        {dot && <span className={styles.tileDot} style={{ background: dot }} aria-hidden />}
        {label}
        {of !== undefined && (
          <span className={styles.tileShare} title={`${label} as a share of all collisions`}>
            {sharePct(value, of)}
          </span>
        )}
      </dt>
      <dd>{value.toLocaleString('en-GB')}</dd>
      {note && <dd className={styles.tileNote}>{note}</dd>}
    </div>
  )
}

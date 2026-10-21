import { type ReactNode, useEffect, useRef, useState } from 'react'

import { RISK_BANDS, type RiskBand } from '../../lib/safety'
import type { SiteFigure, SiteSectionId } from '../../lib/site'
import traffic from '../traffic/traffic.module.css'
import styles from './site.module.css'
import type { ApiFilter } from '../../lib/filter'
import { DataIssueNote } from '../dataIssues/DataIssueNote'

export interface SiteSection {
  id: SiteSectionId
  label: string
  /** For the index, when the heading is long. */
  short?: string
  content: ReactNode
}

interface SiteShellProps {
  eyebrow: string
  wide: boolean
  onToggleWide: () => void
  onClose: () => void
  children: ReactNode
  busy?: boolean
}

/** The panel around a junction or road site page: eyebrow, width toggle, close. */
export function SiteShell({ eyebrow, wide, onToggleWide, onClose, children, busy }: SiteShellProps) {
  return (
    <aside className={traffic.panel} aria-label={eyebrow}>
      <header className={traffic.head}>
        <div className={traffic.headTop}>
          <p className="eyebrow">{eyebrow}</p>
          <div className={styles.headActions}>
            <button type="button" className={styles.widthToggle} aria-pressed={wide} onClick={onToggleWide}>
              {wide ? 'Narrow panel' : 'Widen panel'}
            </button>
            <button
              type="button"
              className={traffic.close}
              onClick={onClose}
              aria-label={`Close ${eyebrow.toLowerCase()}`}
            >
              ×
            </button>
          </div>
        </div>
      </header>
      <div className={traffic.body} data-site-scroller aria-busy={busy}>
        {children}
      </div>
    </aside>
  )
}

interface SitePageProps {
  /** "Roundabout · 4 arms", "Count point 37882 · Trunk A road". */
  kicker: string
  title: string
  subtitle?: string | null
  chips?: ReactNode
  overlaps?: ReactNode
  figures: SiteFigure[]
  figuresNote?: string
  sections: SiteSection[]
  wide: boolean
  stale?: boolean
  /** Above the header (e.g. "← All sites"). */
  before?: ReactNode
  /** The site's collisions: marks DfT documented data issues among them (FU-049). */
  issuesFilter?: ApiFilter | null
}

/**
 * One skeleton for every kind of site (PLAN-009 V3): header and overlaps, headline
 * figures, then the sections in a fixed order with an index. Wide, the index is a
 * sticky column; narrow or on a phone, a sticky row of links above the sections.
 */
export function SitePage(props: SitePageProps) {
  const {
    kicker,
    title,
    subtitle,
    chips,
    overlaps,
    figures,
    figuresNote,
    sections,
    wide,
    stale,
    before,
    issuesFilter,
  } = props
  const active = useActiveSection(sections.map((s) => s.id))
  return (
    <article className={`${styles.page} ${stale ? traffic.stale : ''}`} data-wide={wide || undefined}>
      {before}
      <header className={styles.head}>
        <p className="eyebrow">{kicker}</p>
        <h2 className={styles.title}>{title}</h2>
        {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
        {chips && <p className={styles.chips}>{chips}</p>}
        {overlaps}
        {issuesFilter && <DataIssueNote filter={issuesFilter} />}
      </header>
      <dl className={styles.figures} data-count={figures.length}>
        {figures.map((f) => (
          <div key={f.label} data-worse={f.worse || undefined}>
            <dt>{f.label}</dt>
            <dd>{f.value}</dd>
            {f.note && <p className={styles.figureNote}>{f.note}</p>}
          </div>
        ))}
      </dl>
      {figuresNote && <p className={styles.figuresNote}>{figuresNote}</p>}
      <div className={styles.layout}>
        <nav className={styles.index} aria-label="Sections">
          <ol>
            {sections.map((s) => (
              <li key={s.id}>
                <a
                  href={`#site-${s.id}`}
                  aria-current={active === s.id ? 'true' : undefined}
                  onClick={(e) => {
                    e.preventDefault()
                    scrollToSection(s.id)
                  }}
                >
                  {s.short ?? s.label}
                </a>
              </li>
            ))}
          </ol>
        </nav>
        <div className={styles.sections}>
          {sections.map((s) => (
            <section key={s.id} id={`site-${s.id}`} className={styles.section} aria-labelledby={`site-${s.id}-h`}>
              <h3 id={`site-${s.id}-h`} className={styles.sectionTitle}>
                {s.label}
              </h3>
              {s.content}
            </section>
          ))}
        </div>
      </div>
    </article>
  )
}

/**
 * Scroll the panel (not the page) to a section. scrollIntoView would also scroll the app
 * shell, whose overflow is hidden, and leave the header off screen.
 */
function scrollToSection(id: string): void {
  const el = document.getElementById(`site-${id}`)
  const scroller = el?.closest<HTMLElement>('[data-site-scroller]')
  if (!el || !scroller) return
  const index = scroller.querySelector<HTMLElement>('nav[aria-label="Sections"]')
  // narrow: the index row is sticky above the sections, so keep the heading below it
  const offset =
    index && getComputedStyle(index).position === 'sticky' && index.offsetWidth > 300 ? index.offsetHeight : 0
  const top = el.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - offset - 8
  const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches
  scroller.scrollTo({ top, behavior: smooth ? 'smooth' : 'auto' })
}

/** The section nearest the top of the scrolling panel, for the index's highlight. */
function useActiveSection(ids: readonly string[]): string | null {
  const [active, setActive] = useState<string | null>(ids[0] ?? null)
  const key = ids.join(',')
  const visible = useRef(new Map<string, number>())
  useEffect(() => {
    const seen = visible.current
    seen.clear()
    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          const id = e.target.id.replace(/^site-/, '')
          if (e.isIntersecting) seen.set(id, e.boundingClientRect.top)
          else seen.delete(id)
        }
        const first = key.split(',').find((id) => seen.has(id))
        if (first) setActive(first)
      },
      { rootMargin: '0px 0px -55% 0px' },
    )
    for (const id of key.split(',')) {
      const el = document.getElementById(`site-${id}`)
      if (el) observer.observe(el)
    }
    return () => observer.disconnect()
  }, [key])
  return active
}

export interface OverlapItem {
  key: string
  label: string
  detail?: string
  band?: RiskBand | null
  onOpen: () => void
}

/** Other sites this one overlaps: a cluster site, the roads on a junction, a road's junctions. */
export function Overlaps({ groups }: { groups: { title: string; items: OverlapItem[] }[] }) {
  const shown = groups.filter((g) => g.items.length > 0)
  if (shown.length === 0) return null
  return (
    <div className={styles.overlaps}>
      {shown.map((g) => (
        <div key={g.title} className={styles.overlapGroup}>
          <span className={styles.overlapTitle}>{g.title}</span>
          <ul>
            {g.items.map((o) => (
              <li key={o.key}>
                <button type="button" className={styles.overlap} onClick={o.onOpen} data-band={o.band ?? undefined}>
                  {o.band !== undefined && <BandSwatch band={o.band} />}
                  {o.label}
                  {o.detail && <span className={styles.overlapDetail}>{o.detail}</span>}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

function BandSwatch({ band }: { band: RiskBand | null }) {
  return (
    <span
      className={styles.swatch}
      style={{ background: RISK_BANDS.find((b) => b.band === band)?.color ?? 'var(--paper-sunk)' }}
      aria-hidden
    />
  )
}

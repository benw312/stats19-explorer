import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'

import { getHealth } from '../lib/api'
import { type DataIssue, getDataIssues, yearsText } from '../lib/dataIssues'
import { WEB_VERSION, versionText } from '../lib/version'
import styles from './about.module.css'

const FORCE_NAMES: Record<number, string> = {
  6: 'Greater Manchester',
  21: 'Staffordshire',
  52: 'Avon and Somerset',
  60: 'North Wales',
  61: 'Gwent',
  62: 'South Wales',
  63: 'Dyfed-Powys',
}

const KIND_WORDS: Record<DataIssue['kind'], string> = {
  under_recording: 'Under-recording',
  incomplete: 'Incomplete records',
  coding: 'Coding change',
  discrepancy: 'Figures differ from local records',
}

/** /about: every caveat behind the app's figures in one place (FU-049). */
export function AboutPage() {
  const data = useQuery({ queryKey: ['data-issues-all'], queryFn: ({ signal }) => getDataIssues(signal) })

  // the page loads its content, so jump to #issue once it's there
  useEffect(() => {
    if (!data.data || !window.location.hash) return
    document.getElementById(decodeURIComponent(window.location.hash.slice(1)))?.scrollIntoView()
  }, [data.data])

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <a className={styles.back} href="/">
          ← STATS19 explorer
        </a>
        <h1 className={styles.title}>About the data</h1>
        <p className={styles.lead}>
          What the app’s figures are built from, how they’re counted, and where the source data has known problems.
        </p>
        <nav aria-label="On this page" className={styles.toc}>
          <a href="#known-issues">Known data issues</a>
          <a href="#recording-gaps">Possible recording gaps</a>
          <a href="#counting">How figures are counted</a>
          <a href="#sources">Sources and licences</a>
          <a href="#version">This copy of the app</a>
        </nav>
      </header>

      <section id="known-issues" className={styles.section} aria-labelledby="known-issues-h">
        <h2 id="known-issues-h">Known data issues (DfT documented)</h2>
        <p>
          The Department for Transport publishes problems it knows about in the police data. The app keeps using the
          published figures, and marks any figure that includes an affected police force and year with{' '}
          <span className={styles.mark}>*</span> <em>DfT documented issue</em>.
        </p>
        {data.isError && <p className={styles.error}>Couldn’t load the list of issues.</p>}
        {data.data && (
          <>
            {data.data.issues.map((i) => (
              <article key={i.id} id={i.id} className={styles.issue}>
                <h3>{i.title}</h3>
                <p className={styles.meta}>
                  {KIND_WORDS[i.kind]} · {i.police_forces.map((f) => FORCE_NAMES[f] ?? `Force ${f}`).join(', ')} ·{' '}
                  {yearsText(range(i.year_from, i.year_to))}
                  {i.affects ? ` · affects ${i.affects.replace('_', ' ')} only` : ''}
                </p>
                <p>{i.summary}</p>
                <blockquote className={styles.quote}>
                  <p>{i.dft_text}</p>
                  <footer>DfT, road casualty statistics: known data issues</footer>
                </blockquote>
              </article>
            ))}
            <p className={styles.small}>
              Source:{' '}
              <a href={data.data.source_url} target="_blank" rel="noopener">
                DfT, road casualty statistics: known data issues
              </a>{' '}
              (DfT last updated {data.data.source_updated}; checked here {data.data.checked}). The list is reviewed each
              September, when DfT publishes the annual statistics.
            </p>
          </>
        )}
      </section>

      <section id="recording-gaps" className={styles.section} aria-labelledby="recording-gaps-h">
        <h2 id="recording-gaps-h">Possible recording gaps (found in the data)</h2>
        <p>
          Separately from DfT’s list, the app looks for authority-years where recorded collisions fall far below the
          authority’s share of Great Britain’s collisions in the three years either side (below 65%, where at least 30 a
          year would be expected). A dip that size is more likely a recording problem than a real fall. These years are
          left out of every rate in Area → Rates (the authority’s own, similar authorities’, the region’s and GB’s), and
          show hollow on the trend.
        </p>
        <p>
          Some may be real: the City of London emptied in 2020, and Wales’s default 20 mph limit from September 2023 may
          explain some falls there. They’re called <em>possible</em> gaps for that reason.
        </p>
        {data.data && data.data.recording_gaps.length > 0 && (
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Authority</th>
                <th scope="col">Year</th>
                <th scope="col" className={styles.num}>
                  Share of its usual level
                </th>
              </tr>
            </thead>
            <tbody>
              {data.data.recording_gaps.map((g) => (
                <tr key={`${g.code}-${g.year}`}>
                  <td>{g.name}</td>
                  <td>{g.year}</td>
                  <td className={styles.num}>{Math.round(g.ratio * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section id="counting" className={styles.section} aria-labelledby="counting-h">
        <h2 id="counting-h">How figures are counted</h2>
        <h3 id="stats19">Collisions and casualties</h3>
        <p>
          STATS19 is the police record of personal-injury road collisions in Great Britain, published by DfT from 1979.
          Damage-only collisions aren’t recorded, and some injury collisions are never reported to the police, so the
          figures are a floor, not a total.
        </p>
        <h3 id="ksi">Severity and adjusted KSI</h3>
        <p>
          KSI means killed or seriously injured. Police forces record serious injuries in different ways (forces using
          the injury-based CRASH system record more as serious), so DfT publishes an <em>adjusted</em> severity: each
          casualty’s probability of being serious. Comparisons between authorities (Area → Rates) and cluster-site
          scores use adjusted severity; counts elsewhere show what the police recorded, with the adjusted figure beside
          the KSI count.
        </p>
        <h3 id="areas">Areas: boundary or police field</h3>
        <p>
          A drawn area or a chosen authority selects collisions by their location (the map boundary). Area → Rates
          counts each authority’s casualties by the police’s own highway authority field, as DfT’s published authority
          figures do. The two differ by a few collisions on boundary roads (at most about 1%).
        </p>
        <h3 id="rates">Rates and similar authorities</h3>
        <p>
          Rates divide casualties by traffic (DfT vehicle-km: major roads from count points and their link lengths,
          minor roads as DfT’s all-roads total less major), by population (ONS mid-year estimates) or by road length.
          Major roads are motorways and A roads. An authority is compared with the 15 most similar authorities{' '}
          <strong>in the same country</strong> (England outside London, London, Wales or Scotland) on population,
          density, traffic per head, major-road share and road length per head: the countries record collisions at very
          different rates, so a cross-border comparison would mostly measure recording.
        </p>
        <h3 id="roads">Roads and junctions</h3>
        <p>
          Each collision is matched to the nearest suitable OS Open Roads link within 25 m, scored on distance, road
          number, class and form of road, following DfT’s network matching study. The police location is trusted; their
          C/unclassified label is only a hint. Junction collisions (recorded at or within 20 m of a junction) go to the
          nearest junction within 25 m. Road rates are per 100 million vehicle-km; junction rates per million vehicles
          entering.
        </p>
        <h3 id="safety">Compared with similar sites</h3>
        <p>
          Safety performance functions (negative binomial, by peer group and region) predict collisions for a road or
          junction’s traffic; Empirical Bayes blends that with its own record. The excess is a screening measure, where
          to look, not proof of a defect.
        </p>
        <h3 id="traffic">Traffic</h3>
        <p>
          DfT annual average daily flows (AADF) by count point. Major roads are counted or estimated every year; minor
          roads only at a sample of points. Each year uses that year’s DfT link length where given.
        </p>
      </section>

      <section id="sources" className={styles.section} aria-labelledby="sources-h">
        <h2 id="sources-h">Sources and licences</h2>
        <ul>
          <li>Road casualty statistics (STATS19), road traffic statistics and value of prevention: DfT, OGL v3.0.</li>
          <li>Population estimates: ONS via Nomis, OGL v3.0. Boundaries: ONS Open Geography, OGL v3.0.</li>
          <li>OS Open Roads, Code-Point Open and Open Names: contains OS data © Crown copyright, OGL v3.0.</li>
          <li>Traffic signals and mini-roundabouts, basemap: © OpenStreetMap contributors, ODbL.</li>
        </ul>
      </section>

      <AppVersion />
    </main>
  )
}

/** Which code is running (FU-050): quote these when reporting a problem. */
function AppVersion() {
  const health = useQuery({ queryKey: ['health'], queryFn: ({ signal }) => getHealth(signal) })
  const api = health.data
    ? health.data.version
      ? versionText(health.data.version)
      : 'unknown (older than this page)'
    : health.isError
      ? 'not reachable'
      : '…'
  return (
    <section id="version" className={styles.section} aria-labelledby="version-h">
      <h2 id="version-h">This copy of the app</h2>
      <p className={styles.small}>Quote these when reporting a problem, with any “ref” shown in an error.</p>
      <dl className={styles.versions}>
        <dt>Web app</dt>
        <dd className="mono">{versionText(WEB_VERSION)}</dd>
        <dt>Data service</dt>
        <dd className="mono">{api}</dd>
      </dl>
    </section>
  )
}

function range(a: number, b: number): number[] {
  return Array.from({ length: b - a + 1 }, (_, i) => a + i)
}

import { formatMoney } from '../../lib/economics'
import {
  type SafetyBlock,
  excessValuePerYear,
  type UnitType,
  formatExcess,
  formatExpected,
  inRegion,
  minorEstimateNote,
  peerGroupLabel,
  standing,
} from '../../lib/safety'
import type { FyrrEntry } from '../../lib/schemes'
import { FyrrCalculator } from '../economics/FyrrCalculator'
import styles from './safety.module.css'

interface SafetyCompareProps {
  unit: UnitType
  s: SafetyBlock
  /** Inside a titled section (the site page): no heading or rule of its own. */
  bare?: boolean
  /** False in PDFs: the scheme return calculator needs inputs. */
  calculator?: boolean
  /** What's typed into the calculator, for "Save as scheme". */
  onFyrrInputs?: (entry: FyrrEntry) => void
}

/** "Compared with similar roads/junctions": predicted, observed, EB-expected, excess. */
export function SafetyCompare({ unit, s, bare = false, calculator = true, onFyrrInputs }: SafetyCompareProps) {
  const noun = unit === 'link' ? 'roads' : 'junctions'
  const group = peerGroupLabel(unit, s.peer_group)
  const period = `${s.year_from}–${s.year_to}`
  return (
    <section
      className={bare ? undefined : styles.compare}
      aria-labelledby={bare ? undefined : `compare-${unit}`}
      aria-label={bare ? `Compared with similar ${noun}` : undefined}
    >
      {!bare && (
        <h3 id={`compare-${unit}`} className={styles.title}>
          Compared with similar {noun}
        </h3>
      )}
      <p className={styles.note}>
        {[group, inRegion(s.region)].filter(Boolean).join(' ')}, {period}
        {unit === 'link' ? ', collisions between junctions' : ''}
      </p>
      {s.predicted === null || s.eb === null || s.excess === null ? (
        <p className={styles.note}>
          Too few similar {noun} to model; observed {s.observed}.
        </p>
      ) : (
        <>
          <dl className={styles.figures}>
            <div>
              <dt>Expected at similar {noun}</dt>
              <dd>{formatExpected(s.predicted)}</dd>
            </div>
            <div>
              <dt>Observed</dt>
              <dd>{s.observed}</dd>
            </div>
            <div>
              <dt>Best estimate here</dt>
              <dd>{formatExpected(s.eb)}</dd>
            </div>
            <div className={styles.excess} data-sign={s.excess >= 0 ? 'worse' : 'better'}>
              <dt>Excess</dt>
              <dd>{formatExcess(s.excess)}</dd>
            </div>
          </dl>
          <p className={styles.verdict}>
            {s.excess >= 0 ? 'More' : 'Fewer'} collisions than similar {noun} carrying this traffic
            {standing(s.excess_rank, s.group_size) ? `: ${standing(s.excess_rank, s.group_size)}` : ''}
            {s.region ? ` ${inRegion(s.region)}` : ''}.
          </p>
          <ExcessValue s={s} />
          {calculator && (
            <FyrrCalculator
              onInputs={onFyrrInputs}
              collisionsPerYear={s.eb / s.years}
              valuePerCollision={s.value_per_collision}
              basis={`On the best estimate of ${formatExpected(s.eb / s.years)} collisions a year here, valued at ${
                s.value_per_collision === null ? '–' : formatMoney(s.value_per_collision)
              } each: DfT’s ${s.price_year ?? ''} value of prevention for the severity mix of ${group}. The estimate already allows for chance highs, so the return isn’t inflated by regression to the mean.`}
            />
          )}
          <p className={styles.note}>
            “Expected” comes from a safety performance function fitted to all {group} (negative binomial on traffic
            {unit === 'link' ? ' and length' : ' entering'}). The best estimate blends it with this site’s own record
            (Empirical Bayes), which corrects for chance highs and lows. Use it to choose where to look, not as proof of
            a defect. Each region gets its own level, because police forces record collisions at very different rates
            (London about three times Scotland on similar roads).
            {s.flag === 'minor_uncounted' ? ` ${minorEstimateNote(s.flow_estimated)}` : ''}
          </p>
        </>
      )}
    </section>
  )
}

/** What the excess costs each year, at DfT values for this peer group's severity mix. */
function ExcessValue({ s }: { s: SafetyBlock }) {
  const { excess, value_per_collision: each } = s
  const value = excessValuePerYear(s, s.years)
  if (excess === null || each === null || value === null || Math.abs(value) < 1) return null
  return (
    <p className={styles.value}>
      {value > 0 ? (
        <>
          The excess is worth about <strong>{formatMoney(value)}</strong> a year
        </>
      ) : (
        <>
          About <strong>{formatMoney(-value)}</strong> a year less than similar sites
        </>
      )}{' '}
      <span className={styles.valueNote}>
        ({formatExcess(excess / s.years)} collisions a year × {formatMoney(each)}, DfT {s.price_year} prices)
      </span>
    </p>
  )
}

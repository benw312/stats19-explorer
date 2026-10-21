import { useEffect, useId, useState } from 'react'

import {
  DEFAULT_REDUCTION_PCT,
  MAX_REDUCTION_PCT,
  formatFyrr,
  formatMoney,
  formatPayback,
  fyrr,
  parseMoney,
} from '../../lib/economics'
import styles from './economics.module.css'

interface FyrrCalculatorProps {
  /** Collisions a year the scheme would act on. */
  collisionsPerYear: number
  valuePerCollision: number | null
  /** One sentence on where the two figures come from. */
  basis: string
  /** Told what's typed, so "Save as scheme" can carry it over (PLAN-011 §4). */
  onInputs?: (entry: { cost: number | null; reductionPct: number | null }) => void
}

/** Scheme cost + expected reduction → first-year rate of return and payback (PLAN-007 B5). */
export function FyrrCalculator({ collisionsPerYear, valuePerCollision, basis, onInputs }: FyrrCalculatorProps) {
  const id = useId()
  const [costText, setCostText] = useState('')
  const [reductionText, setReductionText] = useState(String(DEFAULT_REDUCTION_PCT))
  const cost = parseMoney(costText)
  const reduction = Number(reductionText)
  useEffect(() => {
    onInputs?.({ cost, reductionPct: reduction > 0 && reduction <= MAX_REDUCTION_PCT ? reduction : null })
  }, [cost, reduction, onInputs])
  if (valuePerCollision === null) return null
  const result = fyrr({ collisionsPerYear, valuePerCollision, reductionPct: reduction, cost: cost ?? 0 })
  const costInvalid = costText.trim() !== '' && cost === null
  const reductionInvalid = !(reduction > 0 && reduction <= MAX_REDUCTION_PCT)
  return (
    <details className={styles.calc}>
      <summary className={styles.summary}>Scheme return (FYRR)</summary>
      <p className={styles.basis}>{basis}</p>
      <div className={styles.inputs}>
        <label htmlFor={`${id}-cost`}>
          Scheme cost
          <input
            id={`${id}-cost`}
            className={styles.input}
            inputMode="decimal"
            placeholder="e.g. 40k"
            value={costText}
            aria-invalid={costInvalid}
            onChange={(e) => setCostText(e.target.value)}
          />
        </label>
        <label htmlFor={`${id}-reduction`}>
          Expected reduction, %
          <input
            id={`${id}-reduction`}
            className={styles.input}
            type="number"
            min={1}
            max={MAX_REDUCTION_PCT}
            step={1}
            value={reductionText}
            aria-invalid={reductionInvalid}
            onChange={(e) => setReductionText(e.target.value)}
          />
        </label>
      </div>
      {costInvalid && <p className={styles.error}>Enter a cost in pounds, like 40000, 40k or 1.2m.</p>}
      {result ? (
        <dl className={styles.results} aria-live="polite">
          <div>
            <dt>Collisions saved a year</dt>
            <dd>
              {result.collisionsSaved >= 10 ? result.collisionsSaved.toFixed(0) : result.collisionsSaved.toFixed(2)}
            </dd>
          </div>
          <div>
            <dt>Value a year</dt>
            <dd>{formatMoney(result.valueSaved)}</dd>
          </div>
          <div className={styles.headline}>
            <dt>First-year rate of return</dt>
            <dd>{formatFyrr(result.fyrrPct)}</dd>
          </div>
          <div>
            <dt>Pays back in</dt>
            <dd>{formatPayback(result.paybackYears)}</dd>
          </div>
        </dl>
      ) : (
        !costInvalid && <p className={styles.basis}>Enter the scheme cost to see its return.</p>
      )}
    </details>
  )
}

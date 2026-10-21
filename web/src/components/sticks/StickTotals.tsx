import { type Stick, manoeuvreGlyph, manoeuvreLabel, rowTotals } from '../../lib/sticks'
import styles from './sticks.module.css'

/** Pattern summary: how many of the sticks share each notable condition. */
export function StickTotals({ sticks }: { sticks: readonly Stick[] }) {
  const t = rowTotals(sticks)
  if (t.n === 0) return null
  const pct = (k: number) => `${Math.round((100 * k) / t.n)}%`

  // most common first-vehicle manoeuvre
  const counts = new Map<string, { label: string; n: number }>()
  for (const s of sticks) {
    const v = s.vehicles[0]
    if (!v) continue
    const g = manoeuvreGlyph(v)
    const prev = counts.get(g)
    counts.set(g, { label: manoeuvreLabel(v), n: (prev?.n ?? 0) + 1 })
  }
  const top = [...counts.values()].sort((a, b) => b.n - a.n)[0]

  const items: [string, number][] = [
    ['KSI', t.ksi],
    ['Dark', t.dark],
    ['Wet / icy', t.wet],
    ['Adverse weather', t.adverseWeather],
    ['At a junction', t.atJunction],
  ]
  return (
    <ul className={styles.totals} aria-label="Patterns across these collisions">
      {items.map(([label, k]) => (
        <li key={label}>
          {label} <strong>{k}</strong>
          <span className={styles.of}>
            /{t.n} · {pct(k)}
          </span>
        </li>
      ))}
      {top && (
        <li>
          Commonest V1 manoeuvre: <strong>{top.label.toLowerCase()}</strong>
          <span className={styles.of}> ×{top.n}</span>
        </li>
      )}
    </ul>
  )
}

import { type ReactNode, useState } from 'react'

import styles from './charts.module.css'

export interface TableView {
  columns: string[]
  rows: (string | number)[][]
}

interface ChartCardProps {
  title: string
  subtitle?: string
  legend?: ReactNode
  table: TableView
  children: ReactNode
}

/** Title, optional legend, the chart, and a table view so no value is gated behind hover. */
export function ChartCard({ title, subtitle, legend, table, children }: ChartCardProps) {
  const [asTable, setAsTable] = useState(false)
  return (
    <section className={styles.card}>
      <header className={styles.cardHead}>
        <div>
          <h3 className={styles.title}>{title}</h3>
          {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
        </div>
        <button
          type="button"
          className={styles.tableToggle}
          aria-pressed={asTable}
          onClick={() => setAsTable(!asTable)}
        >
          {asTable ? 'Chart' : 'Table'}
        </button>
      </header>
      {legend && !asTable && <div className={styles.legend}>{legend}</div>}
      {asTable ? <DataTable table={table} /> : children}
    </section>
  )
}

function DataTable({ table }: { table: TableView }) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            {table.columns.map((c, i) => (
              <th key={c} scope="col" className={i > 0 ? styles.num : undefined}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row) => (
            <tr key={String(row[0])}>
              {row.map((cell, i) => (
                <td key={i} className={i > 0 ? styles.num : undefined}>
                  {typeof cell === 'number' ? cell.toLocaleString('en-GB') : cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function SwatchKey({ items }: { items: { label: string; color: string }[] }) {
  return (
    <ul className={styles.key}>
      {items.map((i) => (
        <li key={i.label}>
          <span className={styles.swatch} style={{ background: i.color }} aria-hidden />
          {i.label}
        </li>
      ))}
    </ul>
  )
}

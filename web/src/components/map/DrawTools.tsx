import type { DrawMode } from './MapView'
import styles from './DrawTools.module.css'

interface DrawToolsProps {
  mode: DrawMode | null
  hasArea: boolean
  onMode: (mode: DrawMode | null) => void
  onClear: () => void
}

const TOOLS: [DrawMode, string, string][] = [
  ['radius', 'Radius', 'Click the map to set a centre, then adjust the radius'],
  ['polygon', 'Polygon', 'Click to add points; click the first point to finish'],
  ['rectangle', 'Rectangle', 'Click two opposite corners'],
]

export function DrawTools({ mode, hasArea, onMode, onClear }: DrawToolsProps) {
  const hint = TOOLS.find(([m]) => m === mode)?.[2]
  return (
    <div className={styles.wrap}>
      <div className={styles.tools} role="toolbar" aria-label="Select an area">
        <span className={styles.label}>Select</span>
        {TOOLS.map(([m, label]) => (
          <button
            key={m}
            type="button"
            aria-pressed={mode === m}
            className={styles.tool}
            onClick={() => onMode(mode === m ? null : m)}
          >
            {label}
          </button>
        ))}
        {hasArea && (
          <button type="button" className={styles.clear} onClick={onClear}>
            Clear
          </button>
        )}
      </div>
      {hint && (
        <p className={styles.hint} role="status">
          {hint} · <kbd>Esc</kbd> to cancel
        </p>
      )}
    </div>
  )
}

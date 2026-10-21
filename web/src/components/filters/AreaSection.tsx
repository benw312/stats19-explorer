import { useQuery } from '@tanstack/react-query'
import { useId } from 'react'

import { listAreas } from '../../lib/api'
import { type AreaSel, type BoundaryType, RADIUS_MAX_M } from '../../lib/filter'
import styles from './FilterSheet.module.css'

const TYPES: [BoundaryType, string][] = [
  ['highway_authority', 'Highway authority'],
  ['district', 'District'],
  ['police_force', 'Police force area'],
]

// Slider steps: fine at small radii, coarse at large ones.
const RADII = [25, 50, 100, 150, 200, 250, 300, 400, 500, 750, 1000, 1500, 2000, 3000, 5000, 10000, RADIUS_MAX_M]

interface AreaSectionProps {
  area: AreaSel | null
  boundaryType: BoundaryType
  onBoundaryType: (t: BoundaryType) => void
  onChange: (area: AreaSel | null) => void
}

function formatRadius(m: number): string {
  return m >= 1000 ? `${(m / 1000).toLocaleString('en-GB')} km` : `${m} m`
}

export function AreaSection({ area, boundaryType, onBoundaryType, onChange }: AreaSectionProps) {
  const id = useId()
  const areas = useQuery({
    queryKey: ['areas', boundaryType],
    queryFn: ({ signal }) => listAreas(boundaryType, signal),
    staleTime: Infinity,
  })

  return (
    <div className={styles.group}>
      {area?.type === 'radius' && (
        <div className={styles.radius}>
          <label htmlFor={`${id}-r`} className={styles.groupTitle}>
            Radius <span className="mono">{formatRadius(area.radiusM)}</span>
          </label>
          <input
            id={`${id}-r`}
            type="range"
            min={0}
            max={RADII.length - 1}
            step={1}
            value={Math.max(
              0,
              RADII.findIndex((r) => r >= area.radiusM),
            )}
            aria-valuetext={formatRadius(area.radiusM)}
            onChange={(e) => onChange({ ...area, radiusM: RADII[Number(e.target.value)] })}
          />
        </div>
      )}
      {area?.type === 'polygon' && <p className={styles.areaNote}>Drawn boundary ({area.ring.length - 1} points)</p>}
      {!area && (
        <p className={styles.hint}>
          Use <strong>Select</strong> on the map to draw a radius, polygon or rectangle, or pick an authority:
        </p>
      )}

      <div className={styles.authority}>
        <label htmlFor={`${id}-t`} className="visually-hidden">
          Boundary type
        </label>
        <select id={`${id}-t`} value={boundaryType} onChange={(e) => onBoundaryType(e.target.value as BoundaryType)}>
          {TYPES.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <label htmlFor={`${id}-a`} className="visually-hidden">
          Authority
        </label>
        <select
          id={`${id}-a`}
          value={area?.type === 'authority' && area.boundaryType === boundaryType ? area.code : ''}
          disabled={!areas.data}
          onChange={(e) => onChange(e.target.value ? { type: 'authority', boundaryType, code: e.target.value } : null)}
        >
          <option value="">{areas.isLoading ? 'Loading…' : 'Choose…'}</option>
          {areas.data?.map((a) => (
            <option key={a.code} value={a.code}>
              {a.name}
            </option>
          ))}
        </select>
      </div>
      {area && (
        <button type="button" className={styles.more} onClick={() => onChange(null)}>
          Clear area
        </button>
      )}
    </div>
  )
}

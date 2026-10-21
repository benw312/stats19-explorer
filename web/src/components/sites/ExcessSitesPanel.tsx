import type { ReactNode } from 'react'

import type { ApiFilter } from '../../lib/filter'
import type { ClusterCircle } from '../../lib/site'
import { ExcessList } from '../safety/ExcessList'
import traffic from '../traffic/traffic.module.css'

interface ExcessSitesPanelProps {
  area: ApiFilter['area']
  areaLabel: string
  clusters: readonly ClusterCircle[]
  methodSwitch: ReactNode
  onCountPoint: (id: number) => void
  onJunction: (id: string) => void
  onClose: () => void
}

/** Sites → "Worse than expected": the ranked EB excess list (the map shows the risk layer). */
export function ExcessSitesPanel(props: ExcessSitesPanelProps) {
  const { area, areaLabel, clusters, methodSwitch, onCountPoint, onJunction, onClose } = props
  return (
    <aside className={traffic.panel} aria-label="Sites">
      <header className={traffic.head}>
        <div className={traffic.headTop}>
          <p className="eyebrow">Sites</p>
          <button type="button" className={traffic.close} onClick={onClose} aria-label="Close sites">
            ×
          </button>
        </div>
        {methodSwitch}
      </header>
      <div className={traffic.body}>
        <ExcessList
          area={area}
          areaLabel={areaLabel}
          clusters={clusters}
          onCountPoint={onCountPoint}
          onJunction={onJunction}
        />
      </div>
    </aside>
  )
}

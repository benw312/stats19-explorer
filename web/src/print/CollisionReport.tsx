import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { Record } from '../components/collision/CollisionPanel'
import { StickDiagram } from '../components/sticks/StickDiagram'
import { StickKey } from '../components/sticks/StickKey'
import { getCollision } from '../lib/api'
import { SEVERITIES } from '../lib/severity'
import { stickFromRecord } from '../lib/sticks'
import { PrintMap } from './PrintMap'
import styles from './print.module.css'
import { GENERATED_ON, signalError, signalReady } from './ready'

const NEARBY_DEG = 0.0035

export function CollisionReport({ id }: { id: string }) {
  const [mapReady, setMapReady] = useState(false)
  const q = useQuery({ queryKey: ['c', id], queryFn: ({ signal }) => getCollision(id, signal) })
  const lon = q.data?.collision.lon
  const lat = q.data?.collision.lat
  const hasPoint = typeof lon === 'number' && typeof lat === 'number'

  useEffect(() => {
    if (q.isError) signalError(q.error instanceof Error ? q.error.message : 'collision request failed')
    else if (q.isSuccess && (mapReady || !hasPoint)) void signalReady()
  }, [q.isError, q.isSuccess, q.error, mapReady, hasPoint])

  if (!q.data) return <p className={styles.loading}>Preparing report…</p>
  const stick = stickFromRecord(q.data.collision, q.data.vehicles, q.data.casualties)

  return (
    <article className={styles.report}>
      <header className={styles.cover}>
        <p className={styles.eyebrow}>STATS19 collision record</p>
        <h1 className={styles.title}>Collision {id}</h1>
        <p className={styles.metaLine}>Generated {GENERATED_ON}</p>
      </header>
      <div className={styles.recordGrid}>
        <div className={styles.recordCard}>
          <Record {...q.data} />
        </div>
        <div>
          {hasPoint && (
            <figure className={styles.mapFigure}>
              <PrintMap
                bbox={[lon - NEARBY_DEG, lat - NEARBY_DEG, lon + NEARBY_DEG, lat + NEARBY_DEG]}
                outline={null}
                points={[{ lon, lat, severity: stick.severity }]}
                height={320}
                onReady={() => setMapReady(true)}
              />
              <figcaption>
                {SEVERITIES.map((sv) => (
                  <span key={sv.code}>
                    <i style={{ background: sv.cssVar }} /> {sv.label}
                  </span>
                ))}
                <span className={styles.attrib}>© OpenStreetMap contributors</span>
              </figcaption>
            </figure>
          )}
          <h2 className={styles.h2}>Stick</h2>
          <div className={styles.sticks}>
            <StickDiagram sticks={[stick]} />
          </div>
        </div>
      </div>
      <div className={styles.keyBlock}>
        <StickKey />
      </div>
      <p className={styles.small}>
        Contains public sector information licensed under the Open Government Licence v3.0 (Department for Transport).
        Contributory / road safety factors are not published in the open data.
      </p>
    </article>
  )
}

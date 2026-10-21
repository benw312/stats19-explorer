import { useEffect, useRef, useState } from 'react'

import type { Bbox } from '../lib/api'
import type { Site } from '../lib/hotspots'
import { type SnapshotPoint, snapshotMap } from './mapSnapshots'
import { signalError } from './ready'

export type PrintPoint = SnapshotPoint

interface PrintMapProps {
  bbox: Bbox
  outline: unknown | null // GeoJSON geometry of the selection, if any
  points: PrintPoint[]
  /** Numbered cluster site circles. */
  sites?: readonly Site[]
  height: number
  maxZoom?: number
  onReady: () => void
}

/**
 * Static map for reports: individual collisions as severity dots (always points,
 * whatever the zoom), the selection outline and any cluster sites. Drawn by the
 * shared snapshot map (mapSnapshots.ts) and shown as an image.
 */
export function PrintMap({ bbox, outline, points, sites = [], height, maxZoom = 17, onReady }: PrintMapProps) {
  const el = useRef<HTMLDivElement>(null)
  const onReadyRef = useRef(onReady)
  const [snapshot, setSnapshot] = useState<string | null>(null)

  useEffect(() => {
    if (!el.current) return
    let cancelled = false
    snapshotMap({ width: el.current.clientWidth, height, bbox, outline, points, sites, maxZoom })
      .then((png) => {
        if (cancelled) return
        setSnapshot(png)
        onReadyRef.current()
      })
      .catch((e: unknown) => signalError(`map failed: ${e instanceof Error ? e.message : String(e)}`))
    return () => {
      cancelled = true
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps -- static map, render once

  if (snapshot)
    return <img src={snapshot} alt="Map of the collisions" style={{ display: 'block', width: '100%', height }} />
  return <div ref={el} style={{ height, width: '100%' }} />
}

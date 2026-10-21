import { type FocusEvent, type MouseEvent, type ReactNode, useCallback, useState } from 'react'

import styles from './charts.module.css'

interface TipState {
  x: number
  y: number
  content: ReactNode
}

type Target = MouseEvent<Element> | FocusEvent<Element>

/** One tooltip per chart, positioned relative to the chart's wrapper (position: relative). */
export function useTooltip() {
  const [tip, setTip] = useState<TipState | null>(null)

  const show = useCallback((e: Target, content: ReactNode) => {
    const el = e.currentTarget as Element
    const wrap = el.closest('[data-tip-root]')
    if (!wrap) return
    const box = el.getBoundingClientRect()
    const root = wrap.getBoundingClientRect()
    setTip({ x: box.left + box.width / 2 - root.left, y: box.top - root.top, content })
  }, [])
  const hide = useCallback(() => setTip(null), [])

  const node = tip ? (
    <div className={styles.tooltip} style={{ left: tip.x, top: tip.y }} role="status">
      {tip.content}
    </div>
  ) : null

  return { show, hide, node }
}

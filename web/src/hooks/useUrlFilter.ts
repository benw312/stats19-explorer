import { useCallback, useEffect, useState } from 'react'

import { type UiFilter, fromSearchParams, isFilterParam, toSearchParams } from '../lib/filter'

/** Filter state mirrored in the URL query string (shareable views; back/forward aware). */
export function useUrlFilter(latestYear: number): [UiFilter, (next: UiFilter) => void] {
  const read = useCallback(
    () => fromSearchParams(new URLSearchParams(window.location.search), latestYear),
    [latestYear],
  )
  const [filter, setFilter] = useState<UiFilter>(read)

  useEffect(() => {
    const onPop = () => setFilter(read())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [read])

  const update = useCallback(
    (next: UiFilter) => {
      setFilter(next)
      // keep other app state in the URL (view, hotspot parameters, site)
      const kept = [...new URLSearchParams(window.location.search)].filter(([k]) => !isFilterParam(k))
      const params = new URLSearchParams([...kept, ...toSearchParams(next, latestYear)])
      replaceQuery(params)
    },
    [latestYear],
  )

  return [filter, update]
}

export function replaceQuery(params: URLSearchParams): void {
  const query = params.toString()
  window.history.replaceState(null, '', `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`)
}

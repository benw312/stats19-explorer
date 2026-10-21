import { useQuery } from '@tanstack/react-query'

import { getSummary } from '../../lib/api'
import type { ApiFilter } from '../../lib/filter'
import { getAreaAt } from '../../lib/site'

/** The site's highway authority (the "what's different" baseline). */
export function useAuthority(lonLat: [number, number] | null) {
  return useQuery({
    queryKey: ['area-at', lonLat?.[0].toFixed(5), lonLat?.[1].toFixed(5)],
    queryFn: ({ signal }) => {
      if (!lonLat) throw new Error('no location')
      return getAreaAt(lonLat[0], lonLat[1], signal)
    },
    enabled: lonLat !== null,
    staleTime: Infinity,
  })
}

/** The site's own summary (by year, road users): shared by the sections that need it. */
export function useSiteSummary(siteFilter: ApiFilter | null) {
  return useQuery({
    queryKey: ['summary', JSON.stringify(siteFilter)],
    queryFn: ({ signal }) => {
      if (!siteFilter) throw new Error('no collisions')
      return getSummary(siteFilter, signal)
    },
    enabled: siteFilter !== null,
  })
}

/** The Sites view's two ways of screening the network (PLAN-009 §3.2). */

export type SiteMethod = 'excess' | 'clusters'

export const SITE_METHODS: readonly { id: SiteMethod; label: string; note: string }[] = [
  {
    id: 'excess',
    label: 'Worse than expected',
    note: 'Junctions and A roads with traffic counts, against similar sites in the region (Empirical Bayes).',
  },
  {
    id: 'clusters',
    label: 'Clusters',
    note: 'Places with the most collisions within a radius, on any road.',
  },
]

/** The "sm" URL value → method; anything else is the default. */
export function parseSiteMethod(raw: string | null): SiteMethod {
  return raw === 'clusters' ? 'clusters' : 'excess'
}

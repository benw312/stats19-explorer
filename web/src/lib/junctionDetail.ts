/**
 * STATS19's 2024 junction coding (junction_detail 13-19) has no roundabout, mini-roundabout or
 * slip road values: those collisions are 0 ("not at junction") in it, back-filled years
 * included (FU-035). The record shows the junction type from whichever field still has it.
 */

type Row = Record<string, unknown>

const NOT_AT_JUNCTION = new Set([0, -1])
/** junction_detail_historic codes the new field drops */
const HISTORIC_ONLY = new Set([1, 2, 5])
const ROUNDABOUT_ROAD_TYPE = 1

const code = (row: Row, field: string): number | null => {
  const v = row[field]
  return typeof v === 'number' ? v : null
}

/** The junction type to show for a collision, or null to fall back to junction_detail's label. */
export function reconciledJunction(row: Row): string | null {
  const detail = code(row, 'junction_detail')
  if (detail !== null && !NOT_AT_JUNCTION.has(detail)) return null
  const historic = code(row, 'junction_detail_historic')
  if (historic !== null && HISTORIC_ONLY.has(historic)) {
    const label = row.junction_detail_historic_label
    return typeof label === 'string' ? label : null
  }
  if (code(row, 'road_type') === ROUNDABOUT_ROAD_TYPE) return 'Roundabout'
  return null
}

export const JUNCTION_CODING_NOTE =
  'Since the 2024 coding, roundabouts, mini-roundabouts and slip roads are recorded as “not at junction” here: use Road type → Roundabout.'

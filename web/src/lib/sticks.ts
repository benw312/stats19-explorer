/**
 * Stick diagram model: recorded STATS19 codes -> pictogram keys, sort orders and
 * row totals. Pure functions only; drawing lives in components/sticks.
 *
 * Design rule: the *usual* state (daylight, fine, dry, not at a junction) is drawn
 * quietly so unusual conditions stand out when sticks are sorted side by side.
 */

export interface StickVehicle {
  vehicle_reference: number
  vehicle_type: number | null
  vehicle_type_label: string | null
  road_user_group: string | null
  vehicle_manoeuvre: number | null
  vehicle_manoeuvre_label: string | null
  vehicle_manoeuvre_historic: number | null
  vehicle_manoeuvre_historic_label: string | null
  first_point_of_impact: number | null
  first_point_of_impact_label: string | null
  skidding_and_overturning: number | null
  skidding_and_overturning_label: string | null
  vehicle_leaving_carriageway: number | null
  vehicle_leaving_carriageway_label: string | null
  hit_object_in_carriageway: number | null
  hit_object_in_carriageway_label: string | null
  hit_object_off_carriageway: number | null
  hit_object_off_carriageway_label: string | null
  junction_location_label: string | null
  sex_of_driver_label: string | null
  age_of_driver: number | null
  age_band_of_driver_label: string | null
}

export interface StickCasualty {
  casualty_reference: number
  casualty_seq: number
  vehicle_reference: number | null
  casualty_class: number | null
  casualty_class_label: string | null
  casualty_severity: number | null
  age_of_casualty: number | null
  age_band_of_casualty_label: string | null
  sex_of_casualty_label: string | null
  road_user_group: string | null
  pedestrian_location_label: string | null
  pedestrian_movement_label: string | null
}

export interface Stick {
  collision_index: string
  collision_date: string
  collision_time: string | null
  day_of_week: number | null
  day_of_week_label: string | null
  severity: number
  light_conditions: number | null
  light_conditions_label: string | null
  weather_conditions: number | null
  weather_conditions_label: string | null
  road_surface_conditions: number | null
  road_surface_conditions_label: string | null
  junction_detail: number | null
  junction_detail_label: string | null
  junction_control_label: string | null
  road_type: number | null
  road_type_label: string | null
  carriageway_hazards: number | null
  carriageway_hazards_label: string | null
  urban_or_rural_area_label: string | null
  speed_limit: number | null
  road: string
  number_of_vehicles: number
  number_of_casualties: number
  lon: number | null
  lat: number | null
  vehicles: StickVehicle[]
  casualties: StickCasualty[]
}

// ---------------------------------------------------------------- conditions

export type LightGlyph = 'day' | 'dark-lit' | 'dark-unlit' | 'dark-none' | 'dark-unknown' | 'unknown'
export const lightGlyph = (code: number | null): LightGlyph =>
  (({ 1: 'day', 4: 'dark-lit', 5: 'dark-unlit', 6: 'dark-none', 7: 'dark-unknown' }) as const)[code ?? -1] ?? 'unknown'

export type WeatherGlyph =
  'fine' | 'rain' | 'snow' | 'fine-wind' | 'rain-wind' | 'snow-wind' | 'fog' | 'other' | 'unknown'
export const weatherGlyph = (code: number | null): WeatherGlyph =>
  (
    ({
      1: 'fine',
      2: 'rain',
      3: 'snow',
      4: 'fine-wind',
      5: 'rain-wind',
      6: 'snow-wind',
      7: 'fog',
      8: 'other',
    }) as const
  )[code ?? -1] ?? 'unknown'

export type SurfaceGlyph = 'dry' | 'wet' | 'snow' | 'ice' | 'flood' | 'oil' | 'mud' | 'unknown'
export const surfaceGlyph = (code: number | null): SurfaceGlyph =>
  (({ 1: 'dry', 2: 'wet', 3: 'snow', 4: 'ice', 5: 'flood', 6: 'oil', 7: 'mud' }) as const)[code ?? -1] ?? 'unknown'

export type JunctionGlyph = 'none' | 't' | 'cross' | 'multi' | 'drive' | 'roundabout' | 'slip' | 'other' | 'unknown'
export function junctionGlyph(s: Pick<Stick, 'junction_detail' | 'road_type'>): JunctionGlyph {
  if (s.road_type === 1) return 'roundabout'
  if (s.road_type === 7 || s.road_type === 12) return 'slip'
  return (
    ({ 0: 'none', 13: 't', 16: 'cross', 17: 'multi', 18: 'drive', 19: 'other' } as const)[s.junction_detail ?? -1] ??
    'unknown'
  )
}

// ---------------------------------------------------------------- vehicles

export type ManoeuvreGlyph =
  | 'ahead'
  | 'bend-left'
  | 'bend-right'
  | 'turn-left'
  | 'turn-right'
  | 'wait-left'
  | 'wait-right'
  | 'u-turn'
  | 'lane-left'
  | 'lane-right'
  | 'overtake-moving'
  | 'overtake-stationary'
  | 'overtake-nearside'
  | 'reverse'
  | 'parked'
  | 'parking'
  | 'waiting'
  | 'slowing'
  | 'moving-off'
  | 'unknown'

const MANOEUVRE: Record<number, ManoeuvreGlyph> = {
  1: 'reverse',
  2: 'parked',
  3: 'waiting',
  4: 'slowing',
  5: 'moving-off',
  6: 'u-turn',
  7: 'turn-left',
  8: 'wait-left',
  9: 'turn-right',
  10: 'wait-right',
  11: 'lane-left',
  12: 'lane-right',
  13: 'overtake-moving',
  14: 'overtake-stationary',
  15: 'overtake-nearside',
  19: 'ahead',
  20: 'parking',
}

/** Pre-2024 records also say whether "going ahead" was on a left/right-hand bend. */
export function manoeuvreGlyph(
  v: Pick<StickVehicle, 'vehicle_manoeuvre' | 'vehicle_manoeuvre_historic'>,
): ManoeuvreGlyph {
  if (v.vehicle_manoeuvre_historic === 16) return 'bend-left'
  if (v.vehicle_manoeuvre_historic === 17) return 'bend-right'
  return MANOEUVRE[v.vehicle_manoeuvre ?? -1] ?? 'unknown'
}

export const manoeuvreLabel = (v: StickVehicle): string =>
  v.vehicle_manoeuvre_historic === 16 || v.vehicle_manoeuvre_historic === 17
    ? (v.vehicle_manoeuvre_historic_label ?? '')
    : (v.vehicle_manoeuvre_label ?? 'Unknown')

export type ImpactSide = 'front' | 'back' | 'offside' | 'nearside'
export const impactSide = (code: number | null): ImpactSide | null =>
  (({ 1: 'front', 2: 'back', 3: 'offside', 4: 'nearside' }) as const)[code ?? -1] ?? null

/** Skid / overturn / jack-knife flag letters (null = nothing recorded). */
export const skidFlag = (code: number | null): string | null =>
  (({ 1: 'S', 2: 'SO', 3: 'J', 4: 'JO', 5: 'O' }) as const)[code ?? -1] ?? null

const ABBREV: Record<string, string> = {
  car: 'Car',
  motorcycle: 'MC',
  pedal_cycle: 'PC',
  bus: 'Bus',
  goods_light: 'Van',
  goods_heavy: 'HGV',
  goods_unknown: 'Gds',
  ppt: 'PPT',
  mobility_scooter: 'MS',
  horse: 'Hrs',
  other: 'Oth',
  unknown: '?',
}

export function vehicleAbbrev(v: Pick<StickVehicle, 'road_user_group' | 'vehicle_type'>): string {
  if (v.vehicle_type === 8 || v.vehicle_type === 108) return 'Taxi'
  return ABBREV[v.road_user_group ?? 'unknown'] ?? '?'
}

/** Left the carriageway or hit a roadside object (run-off context worth flagging). */
export const leftRoad = (v: StickVehicle): boolean =>
  (v.vehicle_leaving_carriageway ?? 0) > 0 && v.vehicle_leaving_carriageway !== 9

// ---------------------------------------------------------------- casualties

export const casualtyMark = (c: StickCasualty): string =>
  (({ 1: 'D', 2: 'P', 3: 'Ped' }) as const)[c.casualty_class ?? -1] ?? '?'

// ---------------------------------------------------------------- sorting

export type StickSort =
  'date' | 'severity' | 'light' | 'surface' | 'weather' | 'junction' | 'speed' | 'time' | 'day' | 'manoeuvre'

export const STICK_SORTS: [StickSort, string][] = [
  ['date', 'Date'],
  ['severity', 'Severity'],
  ['light', 'Light'],
  ['surface', 'Road surface'],
  ['weather', 'Weather'],
  ['junction', 'Junction'],
  ['speed', 'Speed limit'],
  ['time', 'Time of day'],
  ['day', 'Day of week'],
  ['manoeuvre', 'Vehicle 1 manoeuvre'],
]

const num = (n: number | null | undefined): number => (n === null || n === undefined || n < 0 ? 999 : n)
const DAY_ORDER = [2, 3, 4, 5, 6, 7, 1] // Monday first

function sortKey(s: Stick, by: StickSort): (number | string)[] {
  switch (by) {
    case 'severity':
      return [s.severity]
    case 'light':
      return [num(s.light_conditions)]
    case 'surface':
      return [num(s.road_surface_conditions)]
    case 'weather':
      return [num(s.weather_conditions)]
    case 'junction':
      return [junctionGlyph(s)]
    case 'speed':
      return [num(s.speed_limit)]
    case 'time':
      return [s.collision_time ?? '99:99']
    case 'day':
      return [DAY_ORDER.indexOf(s.day_of_week ?? 0)]
    case 'manoeuvre':
      return [s.vehicles[0] ? manoeuvreGlyph(s.vehicles[0]) : 'zzz']
    default:
      return []
  }
}

/** New array sorted by the chosen row, then by date (stable, never mutates). */
export function sortSticks(sticks: readonly Stick[], by: StickSort): Stick[] {
  const keyed = sticks.map((s) => ({
    s,
    k: [...sortKey(s, by), s.collision_date, s.collision_time ?? '', s.collision_index],
  }))
  keyed.sort((a, b) => {
    for (let i = 0; i < a.k.length; i++) {
      if (a.k[i] < b.k[i]) return -1
      if (a.k[i] > b.k[i]) return 1
    }
    return 0
  })
  return keyed.map(({ s }) => s)
}

// ---------------------------------------------------------------- totals

export interface RowTotals {
  n: number
  fatal: number
  serious: number
  slight: number
  ksi: number
  dark: number
  adverseWeather: number
  wet: number
  atJunction: number
}

export function rowTotals(sticks: readonly Stick[]): RowTotals {
  const count = (pred: (s: Stick) => boolean) => sticks.filter(pred).length
  const fatal = count((s) => s.severity === 1)
  const serious = count((s) => s.severity === 2)
  return {
    n: sticks.length,
    fatal,
    serious,
    slight: count((s) => s.severity === 3),
    ksi: fatal + serious,
    dark: count((s) => (s.light_conditions ?? 0) >= 4 && (s.light_conditions ?? 0) <= 7),
    adverseWeather: count((s) => (s.weather_conditions ?? 0) >= 2 && (s.weather_conditions ?? 0) <= 7),
    wet: count((s) => (s.road_surface_conditions ?? 0) >= 2 && (s.road_surface_conditions ?? 0) <= 5),
    atJunction: count((s) => junctionGlyph(s) !== 'none' && junctionGlyph(s) !== 'unknown'),
  }
}

// ---------------------------------------------------------------- adapters

type DecodedRow = Record<string, string | number | boolean | null>

const n = (v: DecodedRow[string] | undefined): number | null => (typeof v === 'number' ? v : null)
const t = (v: DecodedRow[string] | undefined): string | null => (v === null || v === undefined ? null : String(v))

/** Road reference as printed on stick diagrams, e.g. "A30", "M5", "A1(M)". */
export function roadRef(cls: number | null, number: number | null, clsLabel: string | null): string {
  if (number && number > 0 && cls !== null && cls >= 1 && cls <= 4) {
    return `${({ 1: 'M', 2: 'A', 3: 'A', 4: 'B' } as Record<number, string>)[cls]}${number}${cls === 2 ? '(M)' : ''}`
  }
  return clsLabel ?? 'Unclassified'
}

/** Build a stick from the /api/collisions/{id} decoded record (single-collision report). */
export function stickFromRecord(c: DecodedRow, vehicles: DecodedRow[], casualties: DecodedRow[]): Stick {
  return {
    collision_index: String(c.collision_index),
    collision_date: String(c.collision_date),
    collision_time: t(c.collision_time)?.slice(0, 5) ?? null,
    day_of_week: n(c.day_of_week),
    day_of_week_label: t(c.day_of_week_label),
    severity: n(c.collision_severity) ?? 3,
    light_conditions: n(c.light_conditions),
    light_conditions_label: t(c.light_conditions_label),
    weather_conditions: n(c.weather_conditions),
    weather_conditions_label: t(c.weather_conditions_label),
    road_surface_conditions: n(c.road_surface_conditions),
    road_surface_conditions_label: t(c.road_surface_conditions_label),
    junction_detail: n(c.junction_detail),
    junction_detail_label: t(c.junction_detail_label),
    junction_control_label: t(c.junction_control_label),
    road_type: n(c.road_type),
    road_type_label: t(c.road_type_label),
    carriageway_hazards: n(c.carriageway_hazards),
    carriageway_hazards_label: t(c.carriageway_hazards_label),
    urban_or_rural_area_label: t(c.urban_or_rural_area_label),
    speed_limit: n(c.speed_limit),
    road: roadRef(n(c.first_road_class), n(c.first_road_number), t(c.first_road_class_label)),
    number_of_vehicles: n(c.number_of_vehicles) ?? vehicles.length,
    number_of_casualties: n(c.number_of_casualties) ?? casualties.length,
    lon: n(c.lon),
    lat: n(c.lat),
    vehicles: vehicles.map((v) => ({
      vehicle_reference: n(v.vehicle_reference) ?? 0,
      vehicle_type: n(v.vehicle_type),
      vehicle_type_label: t(v.vehicle_type_label),
      road_user_group: t(v.road_user_group),
      vehicle_manoeuvre: n(v.vehicle_manoeuvre),
      vehicle_manoeuvre_label: t(v.vehicle_manoeuvre_label),
      vehicle_manoeuvre_historic: n(v.vehicle_manoeuvre_historic),
      vehicle_manoeuvre_historic_label: t(v.vehicle_manoeuvre_historic_label),
      first_point_of_impact: n(v.first_point_of_impact),
      first_point_of_impact_label: t(v.first_point_of_impact_label),
      skidding_and_overturning: n(v.skidding_and_overturning),
      skidding_and_overturning_label: t(v.skidding_and_overturning_label),
      vehicle_leaving_carriageway: n(v.vehicle_leaving_carriageway),
      vehicle_leaving_carriageway_label: t(v.vehicle_leaving_carriageway_label),
      hit_object_in_carriageway: n(v.hit_object_in_carriageway),
      hit_object_in_carriageway_label: t(v.hit_object_in_carriageway_label),
      hit_object_off_carriageway: n(v.hit_object_off_carriageway),
      hit_object_off_carriageway_label: t(v.hit_object_off_carriageway_label),
      junction_location_label: t(v.junction_location_label),
      sex_of_driver_label: t(v.sex_of_driver_label),
      age_of_driver: n(v.age_of_driver),
      age_band_of_driver_label: t(v.age_band_of_driver_label),
    })),
    casualties: casualties.map((k) => ({
      casualty_reference: n(k.casualty_reference) ?? 0,
      casualty_seq: n(k.casualty_seq) ?? 1,
      vehicle_reference: n(k.vehicle_reference),
      casualty_class: n(k.casualty_class),
      casualty_class_label: t(k.casualty_class_label),
      casualty_severity: n(k.casualty_severity),
      age_of_casualty: n(k.age_of_casualty),
      age_band_of_casualty_label: t(k.age_band_of_casualty_label),
      sex_of_casualty_label: t(k.sex_of_casualty_label),
      road_user_group: t(k.road_user_group),
      pedestrian_location_label: t(k.pedestrian_location_label),
      pedestrian_movement_label: t(k.pedestrian_movement_label),
    })),
  }
}

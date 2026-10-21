import { describe, expect, it } from 'vitest'

import {
  type Stick,
  type StickVehicle,
  impactSide,
  lightGlyph,
  manoeuvreGlyph,
  rowTotals,
  sortSticks,
  surfaceGlyph,
  vehicleAbbrev,
  weatherGlyph,
} from './sticks'
import * as sticksModule from './sticks'

const vehicle = (over: Partial<StickVehicle> = {}): StickVehicle => ({
  vehicle_reference: 1,
  vehicle_type: 9,
  vehicle_type_label: 'Car',
  road_user_group: 'car',
  vehicle_manoeuvre: 19,
  vehicle_manoeuvre_label: 'Going ahead',
  vehicle_manoeuvre_historic: 18,
  vehicle_manoeuvre_historic_label: 'Going ahead other',
  first_point_of_impact: 1,
  first_point_of_impact_label: 'Front',
  skidding_and_overturning: 0,
  skidding_and_overturning_label: 'None',
  vehicle_leaving_carriageway: 0,
  vehicle_leaving_carriageway_label: 'Did not leave carriageway',
  hit_object_in_carriageway: 0,
  hit_object_in_carriageway_label: 'None',
  hit_object_off_carriageway: 0,
  hit_object_off_carriageway_label: 'None',
  junction_location_label: null,
  sex_of_driver_label: 'Male',
  age_of_driver: 40,
  age_band_of_driver_label: '36 - 45',
  ...over,
})

const stick = (over: Partial<Stick> = {}): Stick => ({
  collision_index: '2024010000001',
  collision_date: '2024-03-12',
  collision_time: '17:40',
  day_of_week: 3,
  day_of_week_label: 'Tuesday',
  severity: 3,
  light_conditions: 1,
  light_conditions_label: 'Daylight',
  weather_conditions: 1,
  weather_conditions_label: 'Fine no high winds',
  road_surface_conditions: 1,
  road_surface_conditions_label: 'Dry',
  junction_detail: 0,
  junction_detail_label: 'Not at junction',
  junction_control_label: null,
  road_type: 6,
  road_type_label: 'Single carriageway',
  carriageway_hazards: 0,
  carriageway_hazards_label: 'None',
  urban_or_rural_area_label: 'Urban',
  speed_limit: 30,
  road: 'A30',
  number_of_vehicles: 1,
  number_of_casualties: 1,
  lon: -3.5,
  lat: 50.7,
  vehicles: [vehicle()],
  casualties: [],
  ...over,
})

describe('pictogram mapping', () => {
  it('maps light codes, keeping daylight quiet', () => {
    expect(lightGlyph(1)).toBe('day')
    expect(lightGlyph(4)).toBe('dark-lit')
    expect(lightGlyph(5)).toBe('dark-unlit')
    expect(lightGlyph(6)).toBe('dark-none')
    expect(lightGlyph(7)).toBe('dark-unknown')
    expect(lightGlyph(-1)).toBe('unknown')
  })

  it('maps weather and surface, with fine/dry as the quiet default', () => {
    expect(weatherGlyph(1)).toBe('fine')
    expect(weatherGlyph(5)).toBe('rain-wind')
    expect(weatherGlyph(7)).toBe('fog')
    expect(surfaceGlyph(1)).toBe('dry')
    expect(surfaceGlyph(2)).toBe('wet')
    expect(surfaceGlyph(4)).toBe('ice')
    expect(surfaceGlyph(9)).toBe('unknown')
  })

  it('maps manoeuvres, preferring the historic bend codes when present', () => {
    expect(manoeuvreGlyph(vehicle({ vehicle_manoeuvre: 9 }))).toBe('turn-right')
    expect(manoeuvreGlyph(vehicle({ vehicle_manoeuvre: 1 }))).toBe('reverse')
    expect(manoeuvreGlyph(vehicle({ vehicle_manoeuvre: 4 }))).toBe('slowing')
    expect(manoeuvreGlyph(vehicle({ vehicle_manoeuvre: 19, vehicle_manoeuvre_historic: 16 }))).toBe('bend-left')
    expect(manoeuvreGlyph(vehicle({ vehicle_manoeuvre: 19, vehicle_manoeuvre_historic: 17 }))).toBe('bend-right')
    expect(manoeuvreGlyph(vehicle({ vehicle_manoeuvre: -1, vehicle_manoeuvre_historic: -1 }))).toBe('unknown')
  })

  it('maps impact side and vehicle abbreviations', () => {
    expect(impactSide(1)).toBe('front')
    expect(impactSide(3)).toBe('offside')
    expect(impactSide(0)).toBeNull()
    expect(vehicleAbbrev(vehicle())).toBe('Car')
    expect(vehicleAbbrev(vehicle({ road_user_group: 'pedal_cycle' }))).toBe('PC')
    expect(vehicleAbbrev(vehicle({ road_user_group: 'car', vehicle_type: 8 }))).toBe('Taxi')
  })
})

describe('sorting', () => {
  const a = stick({ collision_index: 'A', collision_date: '2024-01-01', light_conditions: 4, severity: 3 })
  const b = stick({ collision_index: 'B', collision_date: '2023-01-01', light_conditions: 1, severity: 1 })
  const c = stick({ collision_index: 'C', collision_date: '2025-01-01', light_conditions: 6, severity: 2 })

  it('sorts by date by default', () => {
    expect(sortSticks([a, b, c], 'date').map((s) => s.collision_index)).toEqual(['B', 'A', 'C'])
  })

  it('groups dark collisions together when sorting by light', () => {
    expect(sortSticks([a, b, c], 'light').map((s) => s.collision_index)).toEqual(['B', 'A', 'C'])
  })

  it('puts the most severe first when sorting by severity', () => {
    expect(sortSticks([a, b, c], 'severity').map((s) => s.collision_index)).toEqual(['B', 'C', 'A'])
  })

  it('does not mutate its input', () => {
    const input = [c, a, b]
    sortSticks(input, 'date')
    expect(input.map((s) => s.collision_index)).toEqual(['C', 'A', 'B'])
  })
})

describe('rowTotals', () => {
  it('counts the notable states per row', () => {
    const sticks = [
      stick({ light_conditions: 4, road_surface_conditions: 2, junction_detail: 13, severity: 2 }),
      stick({ light_conditions: 1, road_surface_conditions: 2, weather_conditions: 2 }),
      stick({ light_conditions: 6, road_surface_conditions: 1 }),
    ]

    const t = rowTotals(sticks)

    expect(t.dark).toBe(2)
    expect(t.wet).toBe(2)
    expect(t.adverseWeather).toBe(1)
    expect(t.atJunction).toBe(1)
    expect(t.ksi).toBe(1)
    expect(t.n).toBe(3)
  })
})

describe('roadRef', () => {
  it('formats classified roads like STATS19 reports', () => {
    const { roadRef } = sticksModule
    expect(roadRef(3, 30, 'A')).toBe('A30')
    expect(roadRef(1, 5, 'Motorway')).toBe('M5')
    expect(roadRef(2, 1, 'A(M)')).toBe('A1(M)')
    expect(roadRef(6, 0, 'Unclassified')).toBe('Unclassified')
  })
})

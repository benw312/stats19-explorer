import { describe, expect, it } from 'vitest'

import { reconciledJunction } from './junctionDetail'

describe('reconciledJunction', () => {
  it('keeps the new junction detail when it has a junction', () => {
    expect(reconciledJunction({ junction_detail: 13, junction_detail_historic: 3, road_type: 6 })).toBeNull()
  })

  it('takes roundabouts, minis and slip roads from the historic field', () => {
    expect(
      reconciledJunction({
        junction_detail: 0,
        junction_detail_historic: 2,
        junction_detail_historic_label: 'Mini-roundabout',
        road_type: 6,
      }),
    ).toBe('Mini-roundabout')
  })

  it('falls back to the road type once the historic field stops (2024+)', () => {
    expect(reconciledJunction({ junction_detail: 0, junction_detail_historic: -1, road_type: 1 })).toBe('Roundabout')
  })

  it('leaves genuine non-junction collisions alone', () => {
    expect(reconciledJunction({ junction_detail: 0, junction_detail_historic: 0, road_type: 6 })).toBeNull()
  })
})

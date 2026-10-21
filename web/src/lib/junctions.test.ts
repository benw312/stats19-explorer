import { describe, expect, it } from 'vitest'

import { armLabel, compass, controlLabel, coverageNote, formatRate, junctionTitle } from './junctions'

describe('armLabel', () => {
  it('shows the road number and name, then the class when it has neither', () => {
    expect(armLabel({ road_number: 'A38', name: 'Exeter Road', road_class: 'A Road', form_of_way: null })).toBe(
      'A38 Exeter Road',
    )
    expect(armLabel({ road_number: 'A38', name: null, road_class: 'A Road', form_of_way: null })).toBe('A38')
    expect(armLabel({ road_number: null, name: 'Mill Lane', road_class: 'Unclassified', form_of_way: null })).toBe(
      'Mill Lane',
    )
    expect(
      armLabel({
        road_number: null,
        name: null,
        road_class: 'Classified Unnumbered',
        form_of_way: 'Single Carriageway',
      }),
    ).toBe('Unnamed C road')
  })

  it('marks slip roads', () => {
    expect(armLabel({ road_number: 'M5', name: null, road_class: 'Motorway', form_of_way: 'Slip Road' })).toBe(
      'M5 slip road',
    )
  })
})

describe('compass', () => {
  it.each([
    [0, 'N'],
    [44, 'NE'],
    [181, 'S'],
    [270, 'W'],
    [350, 'N'],
    [-90, 'W'],
  ])('%i degrees is %s', (bearing, point) => {
    expect(compass(bearing)).toBe(point)
  })
})

describe('junctionTitle', () => {
  it('leads with the motorway junction number', () => {
    expect(junctionTitle({ name: 'M5 / A377', motorway_junction: 'M5 J30', kind_label: 'Roundabout' })).toBe(
      'M5 J30 · M5 / A377',
    )
  })

  it('names unnamed junctions by type', () => {
    expect(junctionTitle({ name: null, motorway_junction: null, kind_label: 'T or Y junction' })).toBe(
      'Unnamed t or y junction',
    )
  })
})

describe('controlLabel', () => {
  it('is unknown without signals data', () => {
    expect(controlLabel({ signalised: null, kind: 't_junction' })).toBeNull()
  })

  it('distinguishes signals, roundabouts and priority junctions', () => {
    expect(controlLabel({ signalised: true, kind: 'roundabout' })).toBe('Traffic signals')
    expect(controlLabel({ signalised: false, kind: 'roundabout' })).toBe('Give way (roundabout)')
    expect(controlLabel({ signalised: false, kind: 'crossroads' })).toBe('Priority / give way')
  })
})

describe('coverageNote', () => {
  it('explains what the flow covers', () => {
    expect(coverageNote({ coverage: 'all', uncounted_major: 0, uncounted_minor: 0 })).toBe('Every arm has a DfT count.')
    expect(coverageNote({ coverage: 'major', uncounted_major: 0, uncounted_minor: 2 })).toMatch(
      /2 minor arms have no count/,
    )
    expect(coverageNote({ coverage: 'partial', uncounted_major: 1, uncounted_minor: 0 })).toMatch(
      /1 major arm has no count, so no rate/,
    )
  })
})

describe('formatRate', () => {
  it('keeps two significant figures or so', () => {
    expect(formatRate(0.0432)).toBe('0.04')
    expect(formatRate(0.493)).toBe('0.49')
    expect(formatRate(2.345)).toBe('2.3')
    expect(formatRate(14.6)).toBe('15')
  })
})

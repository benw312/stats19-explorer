import { describe, expect, it } from 'vitest'

import { type DataIssue, issueHref, issueYears, yearsText } from './dataIssues'

const issue = (id: string, years: number[]): DataIssue => ({
  id,
  title: id,
  police_forces: [21],
  year_from: 2017,
  year_to: 2023,
  kind: 'under_recording',
  summary: '',
  dft_text: '',
  affects: null,
  years,
})

describe('yearsText', () => {
  it('shows a run as a range and gaps as a list', () => {
    expect(yearsText([2023, 2021, 2022])).toBe('2021–2023')
    expect(yearsText([2018, 2020])).toBe('2018, 2020')
    expect(yearsText([2022])).toBe('2022')
  })
})

describe('issueYears', () => {
  it('maps each affected year to the issues covering it', () => {
    const got = issueYears([issue('a', [2021, 2022]), issue('b', [2022])])
    expect(got.get(2021)).toEqual(['a'])
    expect(got.get(2022)).toEqual(['a', 'b'])
    expect(got.has(2023)).toBe(false)
  })
})

it('links to the issue on the About the data page', () => {
  expect(issueHref('avon-somerset-2022')).toBe('/about#avon-somerset-2022')
})

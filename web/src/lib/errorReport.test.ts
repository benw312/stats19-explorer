import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { errorMessage } from './api'
import { newRef, reportError, resetErrorReports } from './errorReport'
import { versionText } from './version'

describe('reportError', () => {
  const fetchMock = vi.fn(() => Promise.resolve(new Response('{}')))

  beforeEach(() => {
    resetErrorReports()
    fetchMock.mockClear()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => vi.unstubAllGlobals())

  const sentBody = (call = 0) =>
    JSON.parse((fetchMock.mock.calls[call] as unknown as [string, RequestInit])[1].body as string)

  it('sends the message, stack, page and version with the reference it returns', () => {
    const ref = reportError('render', new TypeError('rate is undefined'), '\n    at RatesTab')

    expect(fetchMock).toHaveBeenCalledOnce()
    const body = sentBody()
    expect(body.ref).toBe(ref)
    expect(body.kind).toBe('render')
    expect(body.message).toBe('rate is undefined')
    expect(body.stack).toContain('at RatesTab')
    expect(body.version).toBe('dev')
  })

  it('sends each distinct error once', () => {
    reportError('error', new Error('same'))
    reportError('error', new Error('same'))
    reportError('error', new Error('different'))

    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('stops after ten reports on one page', () => {
    for (let i = 0; i < 15; i++) reportError('error', new Error(`e${i}`))

    expect(fetchMock).toHaveBeenCalledTimes(10)
  })

  it('cuts long messages to what the API accepts', () => {
    reportError('error', new Error('x'.repeat(2000)))

    expect(sentBody().message).toHaveLength(500)
  })

  it('copes with non-Error values', () => {
    reportError('unhandledrejection', 'plain string')

    expect(sentBody().message).toBe('plain string')
    expect(sentBody().stack).toBeNull()
  })
})

describe('newRef', () => {
  it('is six lower-case hex characters', () => {
    expect(newRef()).toMatch(/^[0-9a-f]{6}$/)
  })
})

describe('errorMessage', () => {
  it('adds the reference to server faults', () => {
    expect(errorMessage(500, { code: 'internal_error', message: 'Something went wrong.', ref: 'a1b2c3' })).toBe(
      'Something went wrong. (ref a1b2c3)',
    )
  })

  it('leaves expected errors as they are', () => {
    expect(errorMessage(404, { code: 'not_found', message: 'Collision not found', ref: 'a1b2c3' })).toBe(
      'Collision not found',
    )
  })

  it('falls back when there is no envelope', () => {
    expect(errorMessage(502, null)).toBe('Request failed (502)')
  })
})

describe('versionText', () => {
  it('shows the commit and the build time in UK time', () => {
    expect(versionText({ commit: '18201cc', built: '2026-10-08T20:15:00Z' })).toBe('18201cc · built 8 Oct 2026, 21:15')
  })

  it('shows just the commit without a build time', () => {
    expect(versionText({ commit: 'dev', built: null })).toBe('dev')
    expect(versionText({ commit: 'abc', built: 'garbage' })).toBe('abc')
  })
})

import { afterEach, describe, expect, it, vi } from 'vitest'

import { errorMessage } from './api'
import { lastErrorRef, reportError, resetErrorReports } from './errorReport'
import { feedbackContext, sendFeedback } from './feedback'

afterEach(() => {
  resetErrorReports()
  vi.unstubAllGlobals()
  window.history.replaceState(null, '', '/')
})

describe('feedbackContext', () => {
  it('captures the full URL, window and version', () => {
    window.history.replaceState(null, '', '/?view=sites&jn=J1#map=15/51.38/-2.36')
    const c = feedbackContext(null)
    expect(c.url).toBe('/?view=sites&jn=J1#map=15/51.38/-2.36')
    expect(c.viewport).toMatch(/^\d+×\d+/)
    expect(c.version).toBe('dev')
    expect(c.error_ref).toBeNull()
  })

  it('quotes the last error reference the user was shown', () => {
    expect(feedbackContext().error_ref).toBeNull()
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(new Response('{}'))),
    )
    const ref = reportError('render', new Error('boom'))
    expect(feedbackContext().error_ref).toBe(ref)
  })

  it('remembers a server fault’s reference once its message is shown', () => {
    errorMessage(500, { code: 'server_error', message: 'Something went wrong', ref: 'abc123' })
    expect(lastErrorRef()).toBe('abc123')
    errorMessage(404, { code: 'not_found', message: 'No such thing', ref: 'def456' })
    expect(lastErrorRef()).toBe('abc123')
  })

  it('drops a reference that isn’t one', () => {
    expect(feedbackContext('<b>').error_ref).toBeNull()
  })
})

describe('sendFeedback', () => {
  it('posts JSON with the context and returns the reference', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify({ success: true, data: { id: 4, ref: 'a1b2c3' }, error: null }), { status: 201 }),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)
    const context = { url: '/', version: 'dev', viewport: '800×600', user_agent: 'x', error_ref: null }

    const sent = await sendFeedback({ kind: 'idea', message: '  More colours  ', contact_ok: false }, context)

    expect(sent).toEqual({ id: 4, ref: 'a1b2c3' })
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/feedback')
    expect(init.method).toBe('POST')
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json')
    expect(JSON.parse(init.body as string)).toEqual({
      ...context,
      kind: 'idea',
      message: 'More colours',
      contact_ok: false,
    })
  })

  it('throws the server’s reason when refused', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              success: false,
              data: null,
              error: { code: 'rate_limited', message: 'Too many changes at once.' },
            }),
            { status: 429 },
          ),
        ),
      ),
    )
    await expect(
      sendFeedback(
        { kind: 'problem', message: 'x', contact_ok: true },
        { url: '/', version: 'dev', viewport: '1×1', user_agent: '', error_ref: null },
      ),
    ).rejects.toThrow('Too many changes at once.')
  })
})

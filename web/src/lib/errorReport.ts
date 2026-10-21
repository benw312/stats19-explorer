/**
 * Browser crashes reported to the API log (FU-050), so they leave a trace on the server.
 *
 * The browser makes up the reference, so the crash screen can show it straight away;
 * the API logs it with the message and stack. Reports are best effort: a failure to
 * report is ignored. Each distinct error is sent once per page, at most MAX_REPORTS in all.
 */

import { WEB_VERSION } from './version'

export type ErrorKind = 'error' | 'unhandledrejection' | 'render'

const MAX_REPORTS = 10
const MAX_MESSAGE = 500
const MAX_STACK = 4000

const sent = new Set<string>()
let lastRef: string | null = null

/** Remember a reference the user has been shown, so feedback can quote it (FU-055). */
export function noteErrorRef(ref: string): void {
  lastRef = ref
}

/** The latest error reference shown on this page, if any. */
export function lastErrorRef(): string | null {
  return lastRef
}

export function newRef(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(3))
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
}

function describe(error: unknown): { message: string; stack: string | null } {
  if (error instanceof Error) return { message: error.message || error.name, stack: error.stack ?? null }
  return { message: typeof error === 'string' ? error : 'Non-error value thrown', stack: null }
}

/** Send one report; returns its reference (also when it wasn't sent). */
export function reportError(kind: ErrorKind, error: unknown, extraStack?: string): string {
  const ref = newRef()
  lastRef = ref
  const { message, stack } = describe(error)
  const key = `${kind}:${message}`
  if (sent.has(key) || sent.size >= MAX_REPORTS) return ref
  sent.add(key)
  const body = {
    ref,
    kind,
    message: message.slice(0, MAX_MESSAGE),
    stack: [stack, extraStack].filter(Boolean).join('\n').slice(0, MAX_STACK) || null,
    url: (window.location.pathname + window.location.search).slice(0, MAX_MESSAGE),
    version: WEB_VERSION.commit.slice(0, 40),
  }
  fetch('/api/client-errors', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    keepalive: true,
  }).catch(() => undefined)
  return ref
}

/** Report uncaught errors and unhandled promise rejections from anywhere on the page. */
export function installErrorReporting(): void {
  window.addEventListener('error', (event) => {
    // resource load failures (img, script) have no error object: not crashes
    if (event.error !== undefined) reportError('error', event.error)
  })
  window.addEventListener('unhandledrejection', (event) => {
    // aborted requests (a filter changed mid-fetch) are routine
    if (event.reason instanceof DOMException && event.reason.name === 'AbortError') return
    reportError('unhandledrejection', event.reason)
  })
}

/** For tests: forget what has been sent. */
export function resetErrorReports(): void {
  sent.clear()
  lastRef = null
}

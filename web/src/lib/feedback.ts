/**
 * Feedback from the app's users (FU-055): what they typed, plus the context needed to
 * reproduce it. The full URL holds the view, area, filters and selected site (PLAN-009 §3.8),
 * so opening it shows the same screen.
 */

import { ApiRequestError, type ApiError } from './api'
import { lastErrorRef } from './errorReport'
import { WEB_VERSION } from './version'

export type FeedbackKind = 'problem' | 'idea' | 'question' | 'liked'

export const FEEDBACK_KINDS: readonly { kind: FeedbackKind; label: string; hint: string }[] = [
  { kind: 'problem', label: 'Problem', hint: 'What did you expect, and what did you see?' },
  { kind: 'idea', label: 'Idea', hint: 'What would you like it to do, and what for?' },
  { kind: 'question', label: 'Question', hint: 'What would you like to know?' },
  { kind: 'liked', label: 'Something I liked', hint: 'What worked well for you?' },
]

export const MAX_MESSAGE = 2000

/** What's sent with the message, all shown in the dialog before sending. */
export interface FeedbackContext {
  url: string
  version: string
  viewport: string
  user_agent: string
  error_ref: string | null
}

const ERROR_REF = /^[0-9a-f]{6,12}$/

export function feedbackContext(errorRef: string | null = lastErrorRef()): FeedbackContext {
  const dpr = window.devicePixelRatio
  return {
    url: (window.location.pathname + window.location.search + window.location.hash).slice(0, 2000),
    version: WEB_VERSION.commit.slice(0, 40),
    viewport: `${window.innerWidth}×${window.innerHeight}${dpr && dpr !== 1 ? ` @${Math.round(dpr * 100) / 100}x` : ''}`,
    user_agent: navigator.userAgent.slice(0, 500),
    error_ref: errorRef && ERROR_REF.test(errorRef) ? errorRef : null,
  }
}

export interface FeedbackInput {
  kind: FeedbackKind
  message: string
  contact_ok: boolean
}

/** Send it; resolves with the reference that matches the API log line. */
export async function sendFeedback(
  input: FeedbackInput,
  context: FeedbackContext,
): Promise<{ id: number; ref: string | null }> {
  let response: Response
  try {
    response = await fetch('/api/feedback', {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...context, ...input, message: input.message.trim() }),
    })
  } catch {
    throw new ApiRequestError(0, { code: 'network', message: 'Cannot reach the STATS19 API' })
  }
  const body = (await response.json().catch(() => null)) as {
    success: boolean
    data: { id: number; ref: string | null } | null
    error: ApiError | null
  } | null
  if (!response.ok || !body?.success || !body.data) throw new ApiRequestError(response.status, body?.error ?? null)
  return body.data
}

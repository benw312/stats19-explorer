import { type FormEvent, useEffect, useId, useMemo, useRef, useState } from 'react'

import { ApiRequestError } from '../../lib/api'
import { FEEDBACK_KINDS, type FeedbackKind, MAX_MESSAGE, feedbackContext, sendFeedback } from '../../lib/feedback'
import styles from './feedback.module.css'

interface FeedbackDialogProps {
  /** From the crash screen: the reference it showed. */
  errorRef?: string | null
  onClose: () => void
}

type State =
  { kind: 'idle' } | { kind: 'busy' } | { kind: 'error'; message: string } | { kind: 'sent'; ref: string | null }

/** Tell us about a problem, an idea, a question or something you liked (FU-055). */
export function FeedbackDialog({ errorRef, onClose }: FeedbackDialogProps) {
  const id = useId()
  const ref = useRef<HTMLDialogElement>(null)
  const [kind, setKind] = useState<FeedbackKind>('problem')
  const [message, setMessage] = useState(errorRef ? 'I was trying to ' : '')
  const [contactOk, setContactOk] = useState(true)
  const [state, setState] = useState<State>({ kind: 'idle' })
  const [tried, setTried] = useState(false)
  // captured once, when the dialog opens: the screen the user is reporting on
  const context = useMemo(() => feedbackContext(errorRef === undefined ? undefined : errorRef), [errorRef])
  const hint = FEEDBACK_KINDS.find((k) => k.kind === kind)?.hint
  const empty = message.trim() === '' || message.trim() === 'I was trying to'

  useEffect(() => {
    ref.current?.showModal()
  }, [])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setTried(true)
    if (empty) return
    setState({ kind: 'busy' })
    try {
      const sent = await sendFeedback({ kind, message, contact_ok: contactOk }, context)
      setState({ kind: 'sent', ref: sent.ref })
    } catch (err: unknown) {
      const why = err instanceof ApiRequestError ? err.message : 'It couldn’t be sent.'
      setState({ kind: 'error', message: `${why} Please try again in a moment.` })
    }
  }

  return (
    <dialog ref={ref} className={styles.dialog} aria-labelledby={`${id}-h`} onClose={onClose}>
      {state.kind === 'sent' ? (
        <div role="status">
          <h2 id={`${id}-h`} className={styles.title}>
            Thanks, it’s sent
          </h2>
          <p className={styles.muted}>
            {state.ref ? (
              <>
                Reference <span className="mono">{state.ref}</span>, if you want to mention it.{' '}
              </>
            ) : null}
            {contactOk ? 'We may get back to you about it.' : 'We won’t contact you about it.'}
          </p>
          <div className={styles.actions}>
            <button type="button" className={styles.primary} onClick={() => ref.current?.close()}>
              Close
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={(e) => void submit(e)} noValidate>
          <h2 id={`${id}-h`} className={styles.title}>
            Feedback
          </h2>
          <p className={styles.muted}>Tell us what’s wrong, what you’d like, or what worked. It takes a minute.</p>

          <fieldset className={styles.kinds}>
            <legend className={styles.srOnly}>What kind of feedback</legend>
            {FEEDBACK_KINDS.map((k) => (
              <label key={k.kind} className={styles.kind}>
                <input
                  type="radio"
                  name={`${id}-kind`}
                  value={k.kind}
                  checked={kind === k.kind}
                  onChange={() => setKind(k.kind)}
                />
                <span>{k.label}</span>
              </label>
            ))}
          </fieldset>

          <label className={styles.field} htmlFor={`${id}-msg`}>
            {kind === 'problem'
              ? 'What happened'
              : kind === 'idea'
                ? 'What you’d like'
                : kind === 'question'
                  ? 'Your question'
                  : 'What you liked'}
          </label>
          <textarea
            id={`${id}-msg`}
            className={styles.message}
            value={message}
            rows={5}
            maxLength={MAX_MESSAGE}
            required
            aria-describedby={`${id}-hint`}
            aria-invalid={tried && empty}
            placeholder={hint}
            onChange={(e) => setMessage(e.target.value)}
            autoFocus
          />
          <p id={`${id}-hint`} className={styles.hint}>
            {tried && empty ? <strong className={styles.problem}>Write a few words first. </strong> : null}
            {hint} {message.length > MAX_MESSAGE - 200 ? `${MAX_MESSAGE - message.length} characters left.` : ''}
          </p>

          <label className={styles.check}>
            <input type="checkbox" checked={contactOk} onChange={(e) => setContactOk(e.target.checked)} />
            OK to contact me about this
          </label>

          <details className={styles.context}>
            <summary>What’s sent with it</summary>
            <dl>
              <dt>This screen</dt>
              <dd className="mono">{context.url}</dd>
              <dt>App version</dt>
              <dd className="mono">{context.version}</dd>
              <dt>Window</dt>
              <dd className="mono">{context.viewport}</dd>
              <dt>Browser</dt>
              <dd className="mono">{context.user_agent}</dd>
              {context.error_ref && (
                <>
                  <dt>Last error</dt>
                  <dd className="mono">ref {context.error_ref}</dd>
                </>
              )}
              <dt>Who</dt>
              <dd>Your sign-in email (or “LAN” on the home network)</dd>
            </dl>
          </details>

          {state.kind === 'error' && (
            <p className={styles.notice} role="alert">
              {state.message}
            </p>
          )}
          <div className={styles.actions}>
            <button type="button" className={styles.secondary} onClick={() => ref.current?.close()}>
              Cancel
            </button>
            <button type="submit" className={styles.primary} disabled={state.kind === 'busy'}>
              {state.kind === 'busy' ? 'Sending…' : 'Send'}
            </button>
          </div>
        </form>
      )}
    </dialog>
  )
}

/** The header's "Feedback" button and its dialog. */
export function FeedbackButton({ className }: { className?: string }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" className={className} aria-haspopup="dialog" onClick={() => setOpen(true)}>
        Feedback
      </button>
      {open && <FeedbackDialog onClose={() => setOpen(false)} />}
    </>
  )
}

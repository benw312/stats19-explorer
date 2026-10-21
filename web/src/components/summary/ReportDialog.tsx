import { type ReactNode, useEffect, useId, useRef, useState } from 'react'

import { ApiRequestError, downloadFile } from '../../lib/api'
import styles from './SummaryPanel.module.css'

interface ReportDialogProps {
  heading: string
  blurb: string
  defaultTitle: string
  /** Report URL for the chosen title and notes. */
  url: (title: string, notes: string) => string
  fallbackName: string
  /** Extra report options, rendered above the title. */
  children?: ReactNode
  onClose: () => void
}

type State = { kind: 'idle' } | { kind: 'busy' } | { kind: 'error'; message: string } | { kind: 'done' }

/** Title + notes for a PDF report, then download it (takes a few seconds). */
export function ReportDialog({
  heading,
  blurb,
  defaultTitle,
  url,
  fallbackName,
  children,
  onClose,
}: ReportDialogProps) {
  const id = useId()
  const dialog = useRef<HTMLDialogElement>(null)
  const [title, setTitle] = useState(defaultTitle)
  const [notes, setNotes] = useState('')
  const [state, setState] = useState<State>({ kind: 'idle' })

  useEffect(() => {
    dialog.current?.showModal()
  }, [])

  const generate = async () => {
    setState({ kind: 'busy' })
    try {
      await downloadFile(url(title.trim(), notes.trim()), fallbackName)
      setState({ kind: 'done' })
    } catch (e: unknown) {
      const message = e instanceof ApiRequestError ? e.message : 'The report could not be generated. Please try again.'
      setState({ kind: 'error', message })
    }
  }

  return (
    <dialog ref={dialog} className={styles.dialog} aria-labelledby={`${id}-h`} onClose={onClose}>
      <form
        method="dialog"
        onSubmit={(e) => {
          e.preventDefault()
          void generate()
        }}
      >
        <h2 id={`${id}-h`} className={styles.dialogTitle}>
          {heading}
        </h2>
        <p className={styles.muted}>{blurb}</p>
        {children}
        <label className={styles.field}>
          Title
          <input value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label className={styles.field}>
          Notes <span className={styles.muted}>(optional; appear on the first page)</span>
          <textarea
            value={notes}
            maxLength={2000}
            rows={5}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="e.g. Purpose of the study, scheme reference, observations"
          />
        </label>
        {state.kind === 'error' && (
          <p className={styles.notice} role="alert">
            {state.message}
          </p>
        )}
        {state.kind === 'done' && (
          <p className={styles.success} role="status">
            Report downloaded.
          </p>
        )}
        <div className={styles.dialogActions}>
          <button type="button" className={styles.secondary} onClick={() => dialog.current?.close()}>
            Close
          </button>
          <button type="submit" className={styles.primary} disabled={state.kind === 'busy'}>
            {state.kind === 'busy' ? 'Generating…' : 'Generate PDF'}
          </button>
        </div>
      </form>
    </dialog>
  )
}

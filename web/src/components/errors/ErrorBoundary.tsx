import { Component, type ErrorInfo, type ReactNode } from 'react'

import { reportError } from '../../lib/errorReport'
import { FeedbackDialog } from '../feedback/FeedbackDialog'
import styles from './ErrorBoundary.module.css'

interface Props {
  children: ReactNode
}

interface State {
  ref: string | null
  telling: boolean
}

/**
 * Catches a crash while drawing the page (FU-050): instead of a blank screen, a message
 * with a reference that matches the API log line.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { ref: null, telling: false }

  static getDerivedStateFromError(): Partial<State> {
    return { ref: '' } // the reference arrives in componentDidCatch
  }

  componentDidCatch(error: unknown, info: ErrorInfo): void {
    this.setState({ ref: reportError('render', error, info.componentStack ?? undefined) })
  }

  render(): ReactNode {
    if (this.state.ref === null) return this.props.children
    return (
      <main className={styles.crash} role="alert">
        <p className="eyebrow">STATS19 explorer</p>
        <h1 className={styles.title}>Something went wrong drawing this page</h1>
        <p className={styles.text}>Reloading usually fixes it. If it keeps happening, quote the reference below.</p>
        <div className={styles.actions}>
          <button type="button" className={styles.reload} onClick={() => window.location.reload()}>
            Reload the page
          </button>
          <button type="button" className={styles.tell} onClick={() => this.setState({ telling: true })}>
            Tell us what you were doing
          </button>
          {this.state.ref && (
            <p className={styles.ref}>
              ref <span className="mono">{this.state.ref}</span>
            </p>
          )}
        </div>
        {this.state.telling && (
          <FeedbackDialog errorRef={this.state.ref || null} onClose={() => this.setState({ telling: false })} />
        )}
      </main>
    )
  }
}

import { useState } from 'react'

import type { FyrrEntry, SchemeDraft } from '../../lib/schemes'
import traffic from '../traffic/traffic.module.css'
import { SchemeForm } from './SchemeForm'

interface SaveSchemeProps {
  /** Null when this site has no footprint to save (the reason is shown). */
  draft: SchemeDraft | null
  unavailable?: string
  /** What the user typed into the site's FYRR calculator. */
  entry?: FyrrEntry | null
  onOpenScheme?: (id: string) => void
  className?: string
}

/** "Save as scheme" on a site page or selection (PLAN-011 §4). */
export function SaveScheme({ draft, unavailable, entry = null, onOpenScheme, className }: SaveSchemeProps) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        type="button"
        className={className ?? traffic.action}
        disabled={draft === null}
        title={draft === null ? unavailable : 'Record a scheme here, to monitor whether it worked'}
        onClick={() => setOpen(true)}
      >
        Save as scheme
      </button>
      {open && draft && (
        <SchemeForm
          mode={{ kind: 'create', draft, entry }}
          onOpen={
            onOpenScheme
              ? (id) => {
                  setOpen(false)
                  onOpenScheme(id)
                }
              : undefined
          }
          onClose={() => setOpen(false)}
        />
      )}
    </>
  )
}

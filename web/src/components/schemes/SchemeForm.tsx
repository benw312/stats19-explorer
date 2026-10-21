import { useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useEffect, useId, useRef, useState } from 'react'

import { DEFAULT_REDUCTION_PCT, formatMoney, parseMoney } from '../../lib/economics'
import {
  type FyrrBasis,
  type FyrrEntry,
  type Scheme,
  type SchemeDraft,
  type SchemeInput,
  SITE_TYPE_LABELS,
  createScheme,
  editScheme,
  fyrrSnapshot,
  getSchemeOptions,
  saveErrorMessage,
} from '../../lib/schemes'
import dialog from '../summary/SummaryPanel.module.css'
import styles from './schemes.module.css'

export type SchemeFormMode =
  { kind: 'create'; draft: SchemeDraft; entry: FyrrEntry | null } | { kind: 'edit'; scheme: Scheme }

interface SchemeFormProps {
  mode: SchemeFormMode
  /** After a create: open the new scheme in the Schemes view. */
  onOpen?: (id: string) => void
  onSaved?: (scheme: Scheme) => void
  onClose: () => void
}

const YEARS = [1, 2, 3, 4, 5]

/** The fields as typed: text until saved, so a half-typed cost isn't lost. */
interface Fields {
  name: string
  measure: string
  description: string
  worksStart: string
  worksEnd: string
  beforeYears: number
  afterYears: number
  cost: string
  reduction: string
}

function initialFields(mode: SchemeFormMode): Fields {
  if (mode.kind === 'edit') {
    const s = mode.scheme
    return {
      name: s.name,
      measure: s.measure,
      description: s.description,
      worksStart: s.works_start ?? '',
      worksEnd: s.works_end ?? '',
      beforeYears: s.before_years,
      afterYears: s.after_years,
      cost: s.cost === null ? '' : String(s.cost),
      reduction: s.fyrr ? String(s.fyrr.reduction_pct) : String(DEFAULT_REDUCTION_PCT),
    }
  }
  const { draft, entry } = mode
  return {
    name: draft.name.slice(0, 200),
    measure: '',
    description: '',
    worksStart: '',
    worksEnd: '',
    beforeYears: 3,
    afterYears: 3,
    cost: entry?.cost != null ? String(entry.cost) : '',
    reduction: String(entry?.reductionPct ?? DEFAULT_REDUCTION_PCT),
  }
}

/** The FYRR basis: the site's, or the one saved with the scheme. */
function basisOf(mode: SchemeFormMode): FyrrBasis | null {
  if (mode.kind === 'create') return mode.draft.fyrr
  const f = mode.scheme.fyrr
  return f
    ? {
        collisionsPerYear: f.collisions_per_year,
        valuePerCollision: f.value_per_collision,
        basis: f.basis ?? '',
        pricesYear: f.prices_year ?? null,
      }
    : null
}

/** Problems the form can see before sending; the server checks again. */
function problems(f: Fields, hasBasis: boolean): string[] {
  const out: string[] = []
  if (!f.name.trim()) out.push('Give the scheme a name.')
  if (!f.measure) out.push('Choose a measure.')
  if (f.cost.trim() && parseMoney(f.cost) === null) out.push('Enter the cost in pounds, like 40000, 40k or 1.2m.')
  if (f.worksStart && f.worksEnd && f.worksEnd < f.worksStart) out.push('The works can’t end before they start.')
  const r = Number(f.reduction)
  if (hasBasis && f.reduction.trim() && !(r > 0 && r <= 100)) out.push('The expected reduction must be 1–100%.')
  return out
}

/** Create a scheme from a site, or edit a saved one (PLAN-011 §4). */
export function SchemeForm({ mode, onOpen, onSaved, onClose }: SchemeFormProps) {
  const id = useId()
  const ref = useRef<HTMLDialogElement>(null)
  const queryClient = useQueryClient()
  const options = useQuery({
    queryKey: ['scheme-options'],
    queryFn: ({ signal }) => getSchemeOptions(signal),
    staleTime: Infinity,
  })
  const [f, setF] = useState<Fields>(() => initialFields(mode))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [shown, setShown] = useState<string[]>([])
  const [saved, setSaved] = useState<Scheme | null>(null)
  const basis = basisOf(mode)
  const set = <K extends keyof Fields>(key: K, value: Fields[K]) => setF((prev) => ({ ...prev, [key]: value }))

  useEffect(() => {
    ref.current?.showModal()
  }, [])

  const input = (): SchemeInput => {
    const base =
      mode.kind === 'create'
        ? { site_type: mode.draft.site_type, site_ref: mode.draft.site_ref, geometry: mode.draft.geometry }
        : { site_type: mode.scheme.site_type, site_ref: mode.scheme.site_ref, geometry: mode.scheme.geometry }
    return {
      ...base,
      name: f.name.trim(),
      description: f.description.trim(),
      measure: f.measure,
      works_start: f.worksStart || null,
      works_end: f.worksEnd || null,
      before_years: f.beforeYears,
      after_years: f.afterYears,
      cost: f.cost.trim() ? parseMoney(f.cost) : null,
      fyrr: fyrrSnapshot(basis, f.reduction.trim() ? Number(f.reduction) : null),
    }
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const found = problems(f, basis !== null)
    setShown(found)
    if (found.length > 0) return
    setBusy(true)
    setError(null)
    try {
      const scheme =
        mode.kind === 'create'
          ? await createScheme(input())
          : await editScheme(mode.scheme.id, input(), mode.scheme.version)
      await queryClient.invalidateQueries({ queryKey: ['schemes'] })
      await queryClient.invalidateQueries({ queryKey: ['scheme-collisions', scheme.id] })
      queryClient.setQueryData(['scheme', scheme.id], scheme)
      onSaved?.(scheme)
      if (mode.kind === 'create') setSaved(scheme)
      else ref.current?.close()
    } catch (err: unknown) {
      setError(saveErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const siteType = mode.kind === 'create' ? mode.draft.site_type : mode.scheme.site_type
  const cost = parseMoney(f.cost)
  const reduction = Number(f.reduction)
  const preview =
    basis && cost && reduction > 0 && reduction <= 100
      ? (basis.collisionsPerYear * reduction * basis.valuePerCollision) / 100 / cost
      : null

  return (
    <dialog ref={ref} className={`${dialog.dialog} ${styles.formDialog}`} aria-labelledby={`${id}-h`} onClose={onClose}>
      {saved ? (
        <div role="status">
          <h2 id={`${id}-h`} className={dialog.dialogTitle}>
            Scheme saved
          </h2>
          <p className={dialog.muted}>
            “{saved.name}” is in the Schemes list. Its collisions are counted from the footprint saved now, so they
            won’t move when the sites are rebuilt.
          </p>
          <div className={dialog.dialogActions}>
            <button type="button" className={dialog.secondary} onClick={() => ref.current?.close()}>
              Close
            </button>
            {onOpen && (
              <button type="button" className={dialog.primary} onClick={() => onOpen(saved.id)}>
                Open in Schemes
              </button>
            )}
          </div>
        </div>
      ) : (
        <form onSubmit={(e) => void submit(e)} noValidate>
          <h2 id={`${id}-h`} className={dialog.dialogTitle}>
            {mode.kind === 'create' ? 'Save as scheme' : 'Edit scheme'}
          </h2>
          <p className={dialog.muted}>
            {SITE_TYPE_LABELS[siteType]}
            {mode.kind === 'create' ? ` · ${mode.draft.footprintNote}` : ' · footprint as saved'}
          </p>

          <label className={dialog.field}>
            Name
            <input value={f.name} maxLength={200} required onChange={(e) => set('name', e.target.value)} />
          </label>
          <label className={dialog.field}>
            Measure
            <select
              className={styles.select}
              value={f.measure}
              required
              onChange={(e) => set('measure', e.target.value)}
              disabled={!options.data}
            >
              <option value="">{options.isError ? 'Couldn’t load the measures' : 'Choose…'}</option>
              {options.data?.measures.map((m) => (
                <option key={m.code} value={m.code}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>

          <fieldset className={styles.fieldset}>
            <legend>Works</legend>
            <div className={styles.pair}>
              <label className={dialog.field}>
                Started
                <input type="date" value={f.worksStart} onChange={(e) => set('worksStart', e.target.value)} />
              </label>
              <label className={dialog.field}>
                Completed
                <input type="date" value={f.worksEnd} onChange={(e) => set('worksEnd', e.target.value)} />
              </label>
              <label className={dialog.field}>
                Years before
                <select
                  className={styles.select}
                  value={f.beforeYears}
                  onChange={(e) => set('beforeYears', Number(e.target.value))}
                >
                  {YEARS.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>
              </label>
              <label className={dialog.field}>
                Years after
                <select
                  className={styles.select}
                  value={f.afterYears}
                  onChange={(e) => set('afterYears', Number(e.target.value))}
                >
                  {YEARS.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p className={styles.hint}>
              The works are left out of both periods. Leave “Completed” blank until they finish.
            </p>
          </fieldset>

          <fieldset className={styles.fieldset}>
            <legend>Cost and expected return</legend>
            <div className={styles.pair}>
              <label className={dialog.field}>
                Cost
                <input
                  inputMode="decimal"
                  placeholder="e.g. 40k"
                  value={f.cost}
                  onChange={(e) => set('cost', e.target.value)}
                />
              </label>
              {basis && (
                <label className={dialog.field}>
                  Expected reduction, %
                  <input
                    type="number"
                    min={1}
                    max={100}
                    step={1}
                    value={f.reduction}
                    onChange={(e) => set('reduction', e.target.value)}
                  />
                </label>
              )}
            </div>
            <p className={styles.hint}>
              {basis
                ? `On ${basis.collisionsPerYear.toFixed(2)} collisions a year at ${formatMoney(basis.valuePerCollision)} each (${basis.basis}).`
                : 'No FYRR basis here: the site has no value of prevention to work from.'}
              {preview !== null && ` Expected first-year return: ${Math.round(preview * 100)}%.`}
            </p>
          </fieldset>

          <label className={dialog.field}>
            Description <span className={dialog.muted}>(optional)</span>
            <textarea
              value={f.description}
              maxLength={5000}
              rows={3}
              onChange={(e) => set('description', e.target.value)}
              placeholder="e.g. Scheme reference, what was built, why"
            />
          </label>

          {(shown.length > 0 || error) && (
            <ul className={`${dialog.notice} ${styles.problems}`} role="alert">
              {shown.map((p) => (
                <li key={p}>{p}</li>
              ))}
              {error && <li>{error}</li>}
            </ul>
          )}
          <div className={dialog.dialogActions}>
            <button type="button" className={dialog.secondary} onClick={() => ref.current?.close()}>
              Cancel
            </button>
            <button type="submit" className={dialog.primary} disabled={busy}>
              {busy ? 'Saving…' : mode.kind === 'create' ? 'Save scheme' : 'Save changes'}
            </button>
          </div>
        </form>
      )}
    </dialog>
  )
}

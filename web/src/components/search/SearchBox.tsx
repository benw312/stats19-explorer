import { useQuery } from '@tanstack/react-query'
import { type KeyboardEvent, useId, useState } from 'react'

import { useDebounce } from '../../hooks/useDebounce'
import { type SearchResult, searchPlaces } from '../../lib/api'
import styles from './SearchBox.module.css'

const TYPE_LABEL: Record<SearchResult['type'], string> = {
  postcode: 'Postcode',
  place: 'Place',
  road: 'Road',
  school: 'School',
  hospital: 'Hospital',
  transport: 'Station',
}

interface SearchBoxProps {
  onPick: (result: SearchResult) => void
}

export function SearchBox({ onPick }: SearchBoxProps) {
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const query = useDebounce(text.trim(), 200)
  const listId = useId()

  const {
    data = [],
    isFetching,
    isError,
  } = useQuery({
    queryKey: ['search', query],
    queryFn: ({ signal }) => searchPlaces(query, signal),
    enabled: query.length >= 2,
    staleTime: 5 * 60_000,
  })

  const pick = (r: SearchResult) => {
    setText(r.label)
    setOpen(false)
    onPick(r)
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!open || data.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((i) => (i + 1) % data.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => (i - 1 + data.length) % data.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      pick(data[active])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const showList = open && query.length >= 2

  return (
    <div className={styles.search}>
      <label htmlFor={`${listId}-input`} className="visually-hidden">
        Search postcode, road or place
      </label>
      <input
        id={`${listId}-input`}
        className={styles.input}
        type="search"
        placeholder="Postcode, road or place — e.g. EX1 1AE, A30, Sidwell Street"
        autoComplete="off"
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-activedescendant={showList && data[active] ? `${listId}-${active}` : undefined}
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          setOpen(true)
          setActive(0)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={onKeyDown}
      />
      {showList && (
        <ul id={listId} role="listbox" className={styles.results}>
          {isError && <li className={styles.empty}>Search is unavailable right now.</li>}
          {!isError && data.length === 0 && (
            <li className={styles.empty}>{isFetching ? 'Searching…' : 'No matches'}</li>
          )}
          {data.map((r, i) => (
            <li
              key={`${r.type}-${r.label}-${r.lon}-${r.lat}`}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              className={styles.result}
              onMouseDown={(e) => e.preventDefault()}
              onMouseEnter={() => setActive(i)}
              onClick={() => pick(r)}
            >
              <span className={styles.kind}>{TYPE_LABEL[r.type]}</span>
              <span className={styles.label}>{r.label}</span>
              {r.sublabel && <span className={styles.sub}>{r.sublabel}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

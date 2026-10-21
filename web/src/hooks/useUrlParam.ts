import { useCallback, useEffect, useState } from 'react'

import { replaceQuery } from './useUrlFilter'

/** One query-string value as state (null when absent). */
export function useUrlParam(key: string): [string | null, (next: string | null) => void] {
  const read = useCallback(() => new URLSearchParams(window.location.search).get(key), [key])
  const [value, setValue] = useState<string | null>(read)

  useEffect(() => {
    const onPop = () => setValue(read())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [read])

  const update = useCallback(
    (next: string | null) => {
      setValue(next)
      const params = new URLSearchParams(window.location.search)
      if (next === null || next === '') params.delete(key)
      else params.set(key, next)
      replaceQuery(params)
    },
    [key],
  )
  return [value, update]
}

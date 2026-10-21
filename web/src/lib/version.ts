/** Which code this web app was built from (FU-050): set by the Docker build, "dev" locally. */

export interface Version {
  commit: string
  built: string | null
}

export const WEB_VERSION: Version = {
  commit: import.meta.env.VITE_COMMIT || 'dev',
  built: import.meta.env.VITE_BUILT || null,
}

/** "18201cc · built 8 Oct 2026, 21:00" */
export function versionText(v: Version): string {
  if (!v.built) return v.commit
  const built = new Date(v.built)
  if (Number.isNaN(built.getTime())) return v.commit
  const when = built.toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/London',
  })
  return `${v.commit} · built ${when}`
}

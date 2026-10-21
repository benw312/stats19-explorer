import { Suspense, lazy } from 'react'

import App from './App'

// Print pages (for the PDF renderer, stats19.reports) pull in MapLibre; load them
// only on /print/... URLs.
const PrintApp = lazy(() => import('./print/PrintApp').then((m) => ({ default: m.PrintApp })))
// About the data (FU-049): a reference page, loaded on its own
const AboutPage = lazy(() => import('./about/AboutPage').then((m) => ({ default: m.AboutPage })))

export function Root() {
  if (window.location.pathname === '/about') {
    return (
      <Suspense fallback={null}>
        <AboutPage />
      </Suspense>
    )
  }
  if (!window.location.pathname.startsWith('/print/')) return <App />
  return (
    <div data-print-root>
      <Suspense fallback={null}>
        <PrintApp />
      </Suspense>
    </div>
  )
}

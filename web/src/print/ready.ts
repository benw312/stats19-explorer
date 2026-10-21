/**
 * Signals for the server-side PDF renderer (stats19.reports.render_pdf), which waits
 * for window.__reportReady and fails fast on window.__reportError.
 */
interface ReportWindow {
  __reportReady?: boolean
  __reportError?: string
}

const w = (): ReportWindow => window as unknown as ReportWindow

export async function signalReady(): Promise<void> {
  await document.fonts.ready
  // two frames so the last layout and the WebGL canvas are painted
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))
  w().__reportReady = true
}

export function signalError(message: string): void {
  w().__reportError = message
  w().__reportReady = true
}

/** Fixed when the print page loads, so every render shows the same timestamp. */
export const GENERATED_ON = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })

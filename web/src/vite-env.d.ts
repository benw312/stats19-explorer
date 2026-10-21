/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** git commit of this build (docker/web.Dockerfile; FU-050) */
  readonly VITE_COMMIT?: string
  /** build time, ISO 8601 */
  readonly VITE_BUILT?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

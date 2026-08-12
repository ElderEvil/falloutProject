/// <reference types="vite-plus/client" />

export {}

// Global constants injected by Vite define
declare global {
  const __APP_VERSION__: string

  interface ImportMetaEnv {
    readonly __APP_VERSION__: string
    readonly VITE_API_BASE_URL?: string
  }

  interface ImportMeta {
    readonly env: ImportMetaEnv
  }
}

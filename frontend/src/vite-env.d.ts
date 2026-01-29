/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly __APP_VERSION__: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

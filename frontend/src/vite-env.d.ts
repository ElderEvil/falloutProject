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

// Augment Vue's existing runtime-core declarations instead of replacing them.
// Vue component shim for TypeScript and lint tools
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}

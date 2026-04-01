/// <reference types="vite-plus/client" />

// Global constants injected by Vite define
declare const __APP_VERSION__: string

interface ImportMetaEnv {
  readonly __APP_VERSION__: string
  readonly VITE_API_BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// Declare vMotion directive from @vueuse/motion
declare module '@vue/runtime-core' {
  export interface GlobalDirectives {
    vMotion: any
  }
}

// Vue component shim for TypeScript and lint tools
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}

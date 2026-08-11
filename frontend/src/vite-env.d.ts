/// <reference types="vite-plus/client" />

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
import '@vue/runtime-core'

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

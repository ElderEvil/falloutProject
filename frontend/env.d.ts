/// <reference types="vite/client" />

// Global constants injected by Vite define
declare const __APP_VERSION__: string

interface ImportMetaEnv {
  VITE_API_BASE_URL: string
  // Add other environment variables as needed
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

import { fileURLToPath, URL } from 'node:url'
import { readFileSync } from 'node:fs'

import { defineConfig } from 'vite-plus'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { visualizer } from 'rollup-plugin-visualizer'

// Read version from package.json
const packageJson = JSON.parse(readFileSync('./package.json', 'utf-8'))
const appVersion = packageJson.version

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  lint: { options: { typeAware: true, typeCheck: false } },
  fmt: {
    printWidth: 100,
    tabWidth: 2,
    useTabs: false,
    semi: false,
    singleQuote: true,
    trailingComma: 'es5',
    bracketSpacing: true,
    arrowParens: 'always',
  },
  staged: {
    '*.{js,ts,tsx,vue}': ['vp lint --fix', 'vp fmt'],
    '*.{json,md,css,html}': 'vp fmt',
  },
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  plugins: [
    vue(),
    tailwindcss(),
    mode === 'analyze' && visualizer({
      filename: 'dist/stats.html',
      template: 'treemap',
      gzipSize: true,
      brotliSize: true,
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@/core': fileURLToPath(new URL('./src/core', import.meta.url)),
      '@/modules': fileURLToPath(new URL('./src/modules', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    allowedHosts: ['localhost', '127.0.0.1', '.local'],
    hmr: {
      protocol: 'ws',
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    target: 'esnext',
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        // Perf: do not reintroduce manualChunks here. Grouping core/components/ui
        // and @iconify into named chunks forced them into the initial preload
        // (~211 kB -> ~177 kB gzip once removed; icons 47.9 -> 6.7 kB gzip).

        // Ensure deterministic chunk names for better caching
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]',
      },
    },
  },
}))

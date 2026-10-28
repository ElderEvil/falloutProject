import { fileURLToPath, URL } from 'node:url'
import { readFile, readFileSync } from 'node:fs'

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
    '*.{js,ts,tsx,vue}': ['vp lint --fix', 'vp fmt --no-error-on-unmatched-pattern'],
    '*.{json,md,css,html}': 'vp fmt --no-error-on-unmatched-pattern',
  },
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  plugins: [
    vue(),
    tailwindcss(),
    {
      name: 'local-map-plate',
      apply: 'serve',
      configureServer(server) {
        // Serve fixed local trial assets, without exposing the ignored directory or
        // copying it into public/ (which would ship it in production builds).
        const assets = new Map([
          [
            '/__dev/map-plate.png',
            {
              file: new URL('../.omo/generated/world-map/flare-terrain-v1.png', import.meta.url),
              type: 'image/png',
            },
          ],
          [
            '/__dev/map-chrome.svg',
            {
              file: new URL('../.omo/generated/world-map/reference-chrome.svg', import.meta.url),
              type: 'image/svg+xml',
            },
          ],
        ])
        server.middlewares.use((request, response, next) => {
          const asset = assets.get(request.url?.split('?')[0] ?? '')
          if (!asset) return next()
          if (request.method !== 'GET' && request.method !== 'HEAD') {
            response.statusCode = 405
            response.end()
            return
          }
          readFile(asset.file, (error, bytes) => {
            if (error) {
              response.statusCode = 404
              response.end()
              return
            }
            response.setHeader('Content-Type', asset.type)
            response.setHeader('Cache-Control', 'no-store')
            response.end(request.method === 'HEAD' ? undefined : bytes)
          })
        })
      },
    },
    mode === 'analyze' &&
      visualizer({
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
      // SQLAdmin is served by FastAPI; AI settings remains a Vue route.
      '^/admin(?:$|/(?!ai-settings))': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
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

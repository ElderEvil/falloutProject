import { fileURLToPath, URL } from 'node:url';
import { readFileSync } from 'node:fs';

import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import tailwindcss from '@tailwindcss/vite';
import ui from '@nuxt/ui/vite';
import { visualizer } from 'rollup-plugin-visualizer';

// Read version from package.json
const packageJson = JSON.parse(readFileSync('./package.json', 'utf-8'));
const appVersion = packageJson.version;

// https://vitejs.dev/config/
export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  plugins: [
    vue(),
    ui(),
    tailwindcss(),
    // Bundle analyzer - run with ANALYZE=true
    process.env.ANALYZE ? visualizer({
      open: true,
      filename: 'dist/stats.html',
      gzipSize: true,
      brotliSize: true,
    }) : null
  ].filter(Boolean) as any,
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@/core': fileURLToPath(new URL('./src/core', import.meta.url)),
      '@/modules': fileURLToPath(new URL('./src/modules', import.meta.url))
    }
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
  build: {
    target: 'esnext',
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // Vue ecosystem
          if (id.includes('node_modules/vue/') || id.includes('node_modules/@vue/')) {
            return 'vue-core'
          }
          if (id.includes('node_modules/vue-router')) {
            return 'vue-router'
          }
          if (id.includes('node_modules/pinia')) {
            return 'pinia'
          }

          // HTTP client
          if (id.includes('node_modules/axios')) {
            return 'axios'
          }

          // Icons
          if (id.includes('node_modules/@iconify')) {
            return 'iconify'
          }

          // UI library
          if (id.includes('node_modules/@nuxt/ui')) {
            return 'nuxt-ui'
          }

          // Tailwind
          if (id.includes('node_modules/tailwindcss')) {
            return 'tailwind'
          }

          // UI Components (now in core)
          if (id.includes('/src/core/components/ui/')) {
            return 'ui-components'
          }

          // Stores
          if (id.includes('/src/stores/') && !id.includes('/src/stores/auth.ts')) {
            return 'stores'
          }

          // Other node_modules go to vendor
          if (id.includes('node_modules')) {
            return 'vendor'
          }
        },

        // Ensure deterministic chunk names for better caching
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]',
      }
    }
  }
});

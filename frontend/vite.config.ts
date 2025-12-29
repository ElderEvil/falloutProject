import { fileURLToPath, URL } from 'node:url';

import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import tailwindcss from '@tailwindcss/vite';
import ui from '@nuxt/ui/vite';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    ui(),
    tailwindcss()
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  build: {
    target: 'esnext',
    rolldownOptions: {
      output: {
        advancedChunks: {
          groups: [
            {
              name(moduleId) {
                if (moduleId.includes('node_modules')) {
                  return 'vendor';
                }
                return null;
              }
            }
          ]
        }
      }
    }
  }
});

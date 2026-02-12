import { fileURLToPath, URL } from 'node:url'
import { mergeConfig, defineConfig as defineVitestConfig, configDefaults } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig as any,
  defineVitestConfig({
    test: {
      environment: 'jsdom',
      exclude: [...configDefaults.exclude, 'e2e/**'],
      root: fileURLToPath(new URL('./', import.meta.url)),
      include: ['tests/**/*.test.ts', 'src/**/__tests__/**/*.test.ts'],
      setupFiles: ['./vitest.setup.ts']
    }
  })
)

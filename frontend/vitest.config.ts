import { fileURLToPath, URL } from 'node:url'
import { mergeConfig, defineConfig as defineVitestConfig } from 'vite-plus'
import { configDefaults } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineVitestConfig({
    test: {
      environment: 'jsdom',
      exclude: configDefaults.exclude,
      root: fileURLToPath(new URL('./', import.meta.url)),
      include: ['tests/**/*.test.ts', 'src/**/__tests__/**/*.test.ts'],
      setupFiles: ['./vitest.setup.ts'],
    },
  })
)

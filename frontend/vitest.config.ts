import { fileURLToPath } from 'node:url'
import { mergeConfig, defineConfig as defineVitestConfig, configDefaults } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineVitestConfig({
    test: {
      environment: 'jsdom',
      exclude: [...configDefaults.exclude, 'e2e/**'],
      root: fileURLToPath(new URL('./', import.meta.url)),
      include: ['tests/**/*.test.ts', 'src/**/__tests__/**/*.test.ts']
    }
  })
)

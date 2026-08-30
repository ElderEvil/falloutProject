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
      coverage: {
        provider: 'v8',
        reporter: ['text', 'json', 'html'],
        reportsDirectory: './coverage',
        include: ['src/**/*.ts', 'src/**/*.vue'],
        exclude: [
          'src/**/*.d.ts',
          'src/**/__tests__/**',
          'src/**/*.test.ts',
          'src/core/types/api.generated.ts',
          'src/main.ts',
          'src/modules/trading/**',
        ],
      },
    },
  })
)

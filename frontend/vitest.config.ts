import { fileURLToPath, URL } from 'node:url'
import { mergeConfig, defineConfig as defineVitestConfig } from 'vite-plus'
import { configDefaults } from 'vite-plus'
import viteConfig from './vite.config'

const resolvedViteConfig =
  typeof viteConfig === 'function' ? viteConfig({ mode: 'test', command: 'serve' }) : viteConfig

const authInterceptorTest = 'tests/unit/core/plugins/axios.test.ts'

export default mergeConfig(
  resolvedViteConfig,
  defineVitestConfig({
    test: {
      environment: 'jsdom',
      exclude: configDefaults.exclude,
      root: fileURLToPath(new URL('./', import.meta.url)),
      maxWorkers: process.env.CI ? undefined : 2,
      setupFiles: ['./vitest.setup.ts'],
      pool: 'vmForks',
      // Recycle retained VM modules without thread teardown's shared GC cost.
      vmMemoryLimit: '768MB',
      isolate: true,
      projects: [
        {
          extends: true,
          test: {
            name: 'unit',
            include: ['tests/**/*.test.ts', 'src/**/__tests__/**/*.test.ts'],
            exclude: [authInterceptorTest],
          },
        },
        {
          extends: true,
          // These tests replace window.location, which VM jsdom makes non-configurable.
          test: { name: 'auth', pool: 'forks', include: [authInterceptorTest] },
        },
      ],
      coverage: {
        provider: 'v8',
        reporter: ['text', 'json', 'json-summary', 'html'],
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
        thresholds: {
          statements: 76,
          branches: 69,
          functions: 70,
          lines: 77,
        },
      },
    },
  })
)

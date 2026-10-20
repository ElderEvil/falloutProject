import { mount, type MountingOptions, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { VueQueryPlugin, type QueryClient } from '@tanstack/vue-query'
import type { App } from 'vue'
import { vi } from 'vitest'
import { createQueryClient } from '@/core/query/queryClient'

/**
 * Centralised stub for `@iconify/vue` so components render icons as inert
 * spans instead of resolving the real iconify runtime. Registered here so
 * test files stop hand-rolling the same `vi.mock` block. Import this helper
 * before any component that pulls in `@iconify/vue`.
 */
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    props: ['icon'],
    template: '<span :data-icon="icon" />',
  },
}))

/**
 * Mount `Component` with the standard unit-test setup: a fresh Pinia (both
 * active and installed as a plugin) plus the `@iconify/vue` Icon stub, and a
 * Vue Query provider. Pass `queryClient` when the test needs to inspect or
 * share the cache; otherwise a fresh production-shaped client is created.
 * Any `global` options from the caller are merged underneath these plugins so
 * stores and queries are always available.
 */
export function mountWithSetup(
  Component: unknown,
  options: MountingOptions<unknown> = {},
  queryClient: QueryClient = createQueryClient()
): VueWrapper {
  const pinia = createPinia()
  setActivePinia(pinia)
  const queryPlugin = {
    install(app: App): void {
      app.use(VueQueryPlugin, { queryClient })
    },
  }
  return mount(Component as never, {
    ...options,
    global: {
      ...options.global,
      plugins: [pinia, queryPlugin, ...(options.global?.plugins ?? [])],
    },
  })
}

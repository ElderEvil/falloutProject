import { mount, type MountingOptions, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { vi } from 'vitest'

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
 * active and installed as a plugin) plus the `@iconify/vue` Icon stub.
 * Any `global` options from the caller are merged underneath the Pinia
 * plugin so stores are always available.
 */
export function mountWithSetup(
  Component: unknown,
  options: MountingOptions<unknown> = {},
): VueWrapper {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(Component as never, {
    ...options,
    global: {
      ...options.global,
      plugins: [pinia, ...(options.global?.plugins ?? [])],
    },
  })
}

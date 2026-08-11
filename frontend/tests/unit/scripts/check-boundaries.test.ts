import { describe, expect, it } from 'vitest'
import { collectModuleSpecifiers, hasModuleDependency } from '../../../scripts/check-boundaries.mjs'

describe('check-boundaries', () => {
  it('detects static imports, re-exports, and dynamic imports from modules', () => {
    const source = `
      import type { AuthUser } from '@/modules/auth/models/auth'
      export { useVaultStore } from '@/modules/vault/stores/vault'
      const loadMap = () => import('@/modules/map/stores/map')
    `

    expect(collectModuleSpecifiers(source)).toEqual([
      '@/modules/auth/models/auth',
      '@/modules/vault/stores/vault',
      '@/modules/map/stores/map',
    ])
    expect(hasModuleDependency(source, 'source.ts')).toBe(true)
  })

  it('reads module specifiers from Vue script blocks without matching template text', () => {
    const source = `
      <script setup lang="ts">
      const loadAuth = () => import('@/modules/auth/stores/auth')
      </script>
      <template>import('@/modules/not-a-script')</template>
    `

    expect(collectModuleSpecifiers(source, 'Example.vue')).toEqual([
      '@/modules/auth/stores/auth',
    ])
  })
})

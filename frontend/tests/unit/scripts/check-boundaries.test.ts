import { describe, expect, it } from 'vitest'
import { collectModuleSpecifiers, hasModuleDependency } from '../../../scripts/check-boundaries.mjs'

describe('check-boundaries', () => {
  it.each(['SCRIPT', 'ScRiPt'])('reads imports from %s blocks', (tag) => {
    expect(
      collectModuleSpecifiers(`<${tag}>import x from '@/modules/auth/x'</${tag}>`, 'Example.vue')
    ).toEqual(['@/modules/auth/x'])
  })

  it.each(['</script >', '</SCRIPT\n>', '</script\t\n bar>'])(
    'accepts whitespace in closing tag %s',
    (closingTag) => {
      expect(
        collectModuleSpecifiers(
          `<script>import x from '@/modules/auth/x'${closingTag}`,
          'Example.vue'
        )
      ).toEqual(['@/modules/auth/x'])
    }
  )

  it('ignores script blocks inside comments', () => {
    expect(
      collectModuleSpecifiers(
        "<!-- <script>import x from '@/modules/auth/x'</script> --><template />",
        'Example.vue'
      )
    ).toEqual([])
  })

  it('reads both normal and setup scripts while preserving source text', () => {
    const source = `<script>export { x } from '@/modules/auth/x'</script>
      <script setup lang="ts">const load = () => import('@/modules/vault/x')</script>
      <template><div>&lt;script&gt;</div></template>`
    expect(collectModuleSpecifiers(source, 'Example.vue')).toEqual([
      '@/modules/auth/x',
      '@/modules/vault/x',
    ])
  })

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

    expect(collectModuleSpecifiers(source, 'Example.vue')).toEqual(['@/modules/auth/stores/auth'])
  })
})

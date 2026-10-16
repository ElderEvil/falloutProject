import { describe, expect, it } from 'vitest'
import { effectScope, ref } from 'vue'
import { isOverlayBlocking, useBlockingOverlay } from '@/core/composables/useBlockingOverlay'

describe('useBlockingOverlay', () => {
  it('reports blocking while a registered overlay is open', () => {
    const scope = effectScope()
    const open = ref(false)

    expect(isOverlayBlocking.value).toBe(false)
    scope.run(() => useBlockingOverlay(open))

    open.value = true
    expect(isOverlayBlocking.value).toBe(true)

    open.value = false
    expect(isOverlayBlocking.value).toBe(false)
    scope.stop()
  })

  it('stays blocking while at least one of several overlays is open', () => {
    const first = effectScope()
    const second = effectScope()
    const firstOpen = ref(true)
    const secondOpen = ref(false)

    first.run(() => useBlockingOverlay(firstOpen))
    second.run(() => useBlockingOverlay(secondOpen))
    expect(isOverlayBlocking.value).toBe(true)

    firstOpen.value = false
    expect(isOverlayBlocking.value).toBe(false)

    secondOpen.value = true
    expect(isOverlayBlocking.value).toBe(true)

    first.stop()
    second.stop()
  })

  it('releases the registration when its scope is disposed', () => {
    const scope = effectScope()
    const open = ref(true)
    scope.run(() => useBlockingOverlay(open))
    expect(isOverlayBlocking.value).toBe(true)

    scope.stop()
    expect(isOverlayBlocking.value).toBe(false)
  })
})

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useIntervalFn, usePreferredReducedMotion } from '@vueuse/core'
import { Button } from '@/core/components/ui/button'
import { useVaultBoyFeedback, VAULT_BOY_FEEDBACK_MS } from '@/core/composables/useVaultBoyFeedback'
import { VAULT_BOY_ANIMATIONS, VAULT_BOY_FRAME_MS } from '@/core/utils/vaultBoyAnimations'
import VaultBoySprite from './VaultBoySprite.vue'

const props = defineProps<{ vaultId: string }>()
const { current, dismiss, clear } = useVaultBoyFeedback()
const index = ref(0)
const ready = ref(false)
const reducedMotion = usePreferredReducedMotion()
const sequence = computed(() =>
  current.value ? VAULT_BOY_ANIMATIONS[current.value.animation].sequence : []
)
const pose = computed(
  () =>
    sequence.value[reducedMotion.value === 'reduce' ? sequence.value.length - 1 : index.value] ?? 0
)
const { pause, resume } = useIntervalFn(
  () => {
    if (index.value < sequence.value.length - 1) index.value += 1
    else pause()
  },
  VAULT_BOY_FRAME_MS,
  { immediate: false }
)

watch(
  () => current.value?.id,
  () => {
    pause()
    index.value = 0
    ready.value = false
  },
  { flush: 'sync' }
)
watch(
  [() => current.value?.id, ready],
  ([id, loaded], _, onCleanup) => {
    if (id === undefined || !loaded) return
    if (reducedMotion.value !== 'reduce') resume()
    const timeout = setTimeout(dismiss, VAULT_BOY_FEEDBACK_MS)
    onCleanup(() => {
      clearTimeout(timeout)
      pause()
    })
  },
  { flush: 'sync' }
)

watch(reducedMotion, (value) => {
  if (value === 'reduce') pause()
})
watch(() => props.vaultId, clear)
watch(
  [current, () => props.vaultId],
  ([event, vaultId]) => {
    if (event && event.vaultId !== vaultId) dismiss()
  },
  { flush: 'sync', immediate: true }
)
onUnmounted(clear)
</script>

<template>
  <Teleport to="body">
    <Transition name="vault-feedback">
      <section
        v-if="current"
        :key="current.id"
        class="vault-boy-feedback pointer-events-none fixed right-[max(1rem,env(safe-area-inset-right))] bottom-[calc(5rem+env(safe-area-inset-bottom))] z-[200] w-64 max-w-[calc(100vw-2rem)]"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        <VaultBoySprite
          :animation="current.animation"
          :pose="pose"
          @ready="ready = true"
          class="ml-auto h-36 w-40 sm:h-40 sm:w-44"
        />
        <div class="relative rounded border border-theme-glow bg-surface-sunken/95 px-3 py-3 pr-9">
          <strong class="block text-sm font-semibold text-theme-primary">{{
            current.title
          }}</strong>
          <p class="mt-1 text-xs leading-relaxed break-words text-theme-primary/90">
            {{ current.message }}
          </p>
          <Button
            variant="ghost"
            size="icon-xs"
            class="pointer-events-auto absolute top-1 right-1"
            aria-label="Dismiss animation"
            @click="dismiss"
            >×</Button
          >
        </div>
      </section>
    </Transition>
  </Teleport>
</template>

<style scoped>
.vault-feedback-enter-active,
.vault-feedback-leave-active {
  transition:
    opacity 180ms ease,
    transform 180ms ease;
}
.vault-feedback-enter-from,
.vault-feedback-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
@media (prefers-reduced-motion: reduce) {
  .vault-feedback-enter-active,
  .vault-feedback-leave-active {
    transition: none;
  }
}
</style>

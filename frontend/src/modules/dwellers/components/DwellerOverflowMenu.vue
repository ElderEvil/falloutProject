<script setup lang="ts">
import { ref, onBeforeUnmount, onMounted } from 'vue'
import { Icon } from '@iconify/vue'

const emit = defineEmits<{
  (e: 'rename'): void
  (e: 'soft-delete'): void
}>()

const open = ref(false)
const root = ref<HTMLElement | null>(null)

function onDocumentClick(event: MouseEvent) {
  if (root.value && !root.value.contains(event.target as Node)) open.value = false
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') open.value = false
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onKeydown)
})

function pick(action: 'rename' | 'soft-delete') {
  open.value = false
  if (action === 'rename') emit('rename')
  else emit('soft-delete')
}
</script>

<template>
  <div ref="root" class="overflow-menu">
    <button
      type="button"
      class="menu-trigger"
      :class="{ open }"
      aria-haspopup="menu"
      :aria-expanded="open"
      aria-label="More dweller actions"
      title="More actions"
      @click="open = !open"
    >
      <Icon icon="mdi:dots-vertical" class="trigger-icon" />
    </button>

    <div v-if="open" class="menu" role="menu">
      <button type="button" class="menu-item" role="menuitem" @click="pick('rename')">
        <Icon icon="mdi:pencil" class="item-icon" />
        Rename
      </button>
      <button type="button" class="menu-item danger" role="menuitem" @click="pick('soft-delete')">
        <Icon icon="mdi:account-remove" class="item-icon" />
        Soft-delete
      </button>
    </div>
  </div>
</template>

<style scoped>
.overflow-menu {
  position: relative;
}

.menu-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  background: transparent;
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  color: var(--color-theme-primary);
  cursor: pointer;
  transition:
    background-color 0.2s,
    border-color 0.2s,
    color 0.2s,
    box-shadow 0.2s,
    opacity 0.2s,
    transform 0.2s;
}

.menu-trigger:hover,
.menu-trigger.open {
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.trigger-icon {
  width: 1.15rem;
  height: 1.15rem;
}

.menu {
  position: absolute;
  top: calc(100% + 0.35rem);
  right: 0;
  z-index: 30;
  min-width: 10rem;
  display: flex;
  flex-direction: column;
  padding: 0.25rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-theme-primary);
  border-radius: 4px;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.6);
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 0.6rem;
  background: transparent;
  border: none;
  border-radius: 3px;
  color: var(--color-theme-primary);
  font-family: inherit;
  font-size: 0.8rem;
  text-align: left;
  cursor: pointer;
}

.menu-item:hover {
  background: color-mix(in srgb, var(--color-theme-primary) 16%, transparent);
}

.menu-item.danger {
  color: var(--color-danger);
}

.menu-item.danger:hover {
  background: color-mix(in srgb, var(--color-danger) 16%, transparent);
}

.item-icon {
  width: 1rem;
  height: 1rem;
}
</style>

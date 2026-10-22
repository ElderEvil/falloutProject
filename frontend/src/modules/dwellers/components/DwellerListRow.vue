<script setup lang="ts">
import { computed } from 'vue'
import type { DwellerShort } from '../models/dweller'
import {
  DWELLER_PORTRAIT_SCALE,
  getDwellerBodySize,
  getDwellerDisplayName,
} from '../models/dweller'
import DwellerPortrait from './DwellerPortrait.vue'
import DwellerMetaBadges from './DwellerMetaBadges.vue'

interface Props {
  dweller: DwellerShort
  /** Whether clicking/keyboard-activating the row emits `activate`. */
  clickable?: boolean
  /** Tighter row for in-room pickers and embedded lists. */
  dense?: boolean
  /** Show race/faction plus non-human state markers. */
  showIdentity?: boolean
}

const { clickable = true, dense = false, showIdentity = false, dweller } = defineProps<Props>()

const rowClass = computed(() => (dense ? 'flex-wrap gap-2 p-1.5' : 'gap-3 p-3'))
const identityClass = computed(() => (dense ? 'w-40' : 'w-44'))
const nameClass = computed(() => (dense ? 'text-sm' : 'text-base'))
const metaClass = computed(() => (dense ? 'text-xs' : 'text-sm'))
const portraitClass = computed(() =>
  dense ? 'h-10 w-10 rounded object-cover' : 'h-16 w-16 rounded object-cover'
)
const fallbackClass = computed(() =>
  dense ? 'h-10 w-10 text-theme-primary/60' : 'h-16 w-16 text-theme-primary/60'
)
const portraitScale = computed(() => DWELLER_PORTRAIT_SCALE[getDwellerBodySize(dweller)])

const emit = defineEmits<{
  (e: 'activate', dwellerId: string): void
}>()

function activate() {
  if (clickable) emit('activate', dweller.id)
}
</script>

<template>
  <li
    class="dweller-list-row flex items-center rounded border border-theme-primary/20 bg-surface-canvas transition-all hover:bg-surface-hover"
    :class="[rowClass, clickable ? 'cursor-pointer' : '', { 'dweller-list-row--dense': dense }]"
    :role="clickable ? 'button' : undefined"
    :tabindex="clickable ? 0 : undefined"
    @click="activate"
    @keydown.enter.prevent="activate"
    @keydown.space.prevent="activate"
  >
    <div class="flex-shrink-0">
      <DwellerPortrait
        :thumbnail-url="dweller.thumbnail_url"
        alt=""
        fallback-icon="mdi:account-circle"
        :image-class="portraitClass"
        :fallback-class="fallbackClass"
        :scale="portraitScale"
      />
    </div>

    <div class="dweller-identity flex min-w-0 flex-col" :class="identityClass">
      <h3 class="truncate font-bold text-terminal-green" :class="nameClass">
        {{ getDwellerDisplayName(dweller) }}
      </h3>
      <p v-if="dense" class="text-theme-primary/60" :class="metaClass">Level {{ dweller.level }}</p>
      <div v-else class="flex flex-wrap items-center gap-2">
        <p class="text-theme-primary/60" :class="metaClass">Level {{ dweller.level }}</p>
        <DwellerMetaBadges :dweller="dweller" :show-identity="showIdentity" />
      </div>
    </div>

    <template v-if="dense">
      <span class="dweller-column-divider" aria-hidden="true"></span>
      <DwellerMetaBadges :dweller="dweller" :show-identity="showIdentity" />
      <span v-if="$slots.middle" class="dweller-column-divider" aria-hidden="true"></span>
      <slot name="middle" />
    </template>
    <slot v-else name="middle" />

    <div class="ml-auto flex items-center gap-2">
      <slot name="actions" />
    </div>
  </li>
</template>

<style scoped>
.dweller-list-row--dense {
  align-items: center;
}

.dweller-column-divider {
  display: inline-block;
  width: 1px;
  align-self: stretch;
  background: color-mix(in srgb, var(--color-theme-glow) 45%, transparent);
}
</style>

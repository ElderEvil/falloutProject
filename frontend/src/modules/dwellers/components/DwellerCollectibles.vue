<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { getStaticImageUrl } from '@/core/utils/image'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { getDwellerCollectibles, type DwellerCollectible } from '../api/collectibles'
import { useDwellerDetailContext } from './DwellerDetailContext'

const ctx = useDwellerDetailContext()
const authStore = useAuthStore()

const items = ref<DwellerCollectible[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
let request = 0

async function load() {
  const dwellerId = ctx.dweller.value?.id
  if (!dwellerId || !authStore.token) return
  const seq = ++request
  loading.value = true
  error.value = null
  try {
    const result = await getDwellerCollectibles(dwellerId)
    if (seq === request) items.value = result
  } catch (err) {
    if (seq === request) error.value = getErrorMessage(err)
  } finally {
    if (seq === request) loading.value = false
  }
}

watch([() => ctx.dweller.value?.id, () => authStore.sessionGeneration], load, { immediate: true })
onBeforeUnmount(() => {
  ++request
})
</script>

<template>
  <div class="collectibles space-y-4">
    <p class="text-xs font-bold tracking-[0.12em] text-theme-primary/60">COLLECTIBLES</p>

    <p v-if="loading" class="text-sm text-theme-primary/60">Loading collectibles…</p>
    <p v-else-if="error" class="text-sm text-theme-danger">{{ error }}</p>
    <p v-else-if="items.length === 0" class="text-sm leading-6 text-theme-primary/60">
      No bobbleheads yet. Clear a site or search the wasteland — the finder keeps the bonus for
      life.
    </p>

    <ul v-else class="grid grid-cols-2 gap-3 sm:grid-cols-3">
      <li
        v-for="item in items"
        :key="item.key"
        class="collectible-card flex flex-col items-center rounded border border-theme-primary/25 bg-surface-sunken p-3 text-center"
      >
        <img
          v-if="getStaticImageUrl(item.image)"
          :src="getStaticImageUrl(item.image)!"
          :alt="item.name"
          class="h-20 w-20 object-contain"
          loading="lazy"
        />
        <Icon v-else icon="mdi:robot-happy" class="h-20 w-20 text-theme-primary/40" />
        <p class="mt-2 text-sm font-bold text-theme-primary">{{ item.name }}</p>
        <p class="text-xs font-bold tracking-[0.08em] text-theme-primary/80">
          PERMANENT +{{ item.amount }} {{ item.stat.toUpperCase() }}
        </p>
        <p class="mt-1 text-[0.7rem] text-theme-primary/50">Found at {{ item.location }}</p>
      </li>
    </ul>
  </div>
</template>

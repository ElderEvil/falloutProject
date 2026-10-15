<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useToast } from '@/core/composables/useToast'
import { useRoomStore } from '@/modules/rooms/stores/room'

/**
 * Compatibility route for the retired standalone Response Teams page.
 *
 * The Response Station room is the only management surface now, so this URL
 * resolves the vault's station and opens it in the vault grid, or explains the
 * build requirement when the vault has none. It deliberately renders no roster.
 */
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const roomStore = useRoomStore()
const toast = useToast()

const vaultId = computed(() => route.params.id as string)
const handled = ref(false)
const disposed = ref(false)

onUnmounted(() => {
  disposed.value = true
})

async function openStationOrExplain(): Promise<void> {
  const id = vaultId.value
  const token = authStore.token
  if (!id || typeof token !== 'string' || !token || handled.value) return

  let result = await roomStore.fetchRooms(id, token)
  if (disposed.value || id !== vaultId.value) return

  // A superseded load lost a race to a newer request; retry so the redirect reads
  // that request's state instead of reporting a load that simply lost the race.
  for (let attempt = 0; result === 'superseded' && attempt < 3; attempt++) {
    result = await roomStore.fetchRooms(id, token)
    if (disposed.value || id !== vaultId.value) return
  }

  handled.value = true

  if (result === 'failed') {
    toast.error('Could not load this vault’s rooms — open it from the vault list.')
    await router.replace({ path: `/vault/${id}` })
    return
  }

  const station = roomStore.rooms.find((room) => room.category.toLowerCase() === 'response')
  if (!station) {
    toast.info(
      'No Response Station in this vault yet — it needs 15 dwellers and 600 caps to build.'
    )
  }
  await router.replace({ path: `/vault/${id}`, query: station ? { roomId: station.id } : {} })
}

watch([vaultId, () => authStore.token], () => void openStationOrExplain(), { immediate: true })
</script>

<template>
  <div class="min-h-screen bg-terminal-background" role="status" aria-live="polite">
    <span class="sr-only">Opening the Response Station…</span>
  </div>
</template>

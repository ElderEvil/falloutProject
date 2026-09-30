<script setup lang="ts">
import { computed, onMounted } from 'vue'
import type { Room } from '../models/room'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import RoomPreviewSection from './RoomPreviewSection.vue'
import ArenaActorSprite from './ArenaActorSprite.vue'
import ArenaModal from './ArenaModal.vue'
import RoomActions from './RoomActions.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useArenaStore } from '../stores/arena'
import { getStaticImageUrl } from '@/core/utils/image'
import type { ArenaFighter } from '../api/arena'

// Actor width as a percentage of the scene box; the sprite keeps the actor
// canvas' intrinsic aspect ratio, so height derives from width (PoC precedent:
// ARENA_SCENE_POC.actorWidthPercent).
const ACTOR_WIDTH_PERCENT = 16

interface UpgradeInfo {
  canUpgrade: boolean
  upgradeCost: number
  nextTier: number
  maxTier: number
}

interface Props {
  room: Room
  vaultId: string
  assignedDwellers: DwellerShort[]
  dwellerCapacity: number
  roomImageUrl: string | null
  upgradeInfo: UpgradeInfo | null
  isUpgrading: boolean
  isDestroying: boolean
  isVaultDoor: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  upgrade: []
  destroy: []
  unassignAll: []
}>()

const authStore = useAuthStore()
const arenaStore = useArenaStore()

onMounted(async () => {
  // Fighter actor payloads are vault-scoped server-side, so a missing token/vault id means "nothing to fetch".
  if (authStore.token && props.vaultId) {
    await arenaStore.fetchState(props.vaultId, authStore.token)
  }
})

// Detail-scene art from the asset manifest drives the live scene; the grid art
// stays as the fallback (contract: detail_scene ?? roomImageUrl ?? imageUrl).

const scene = computed(() => props.room.detail_scene ?? null)

const sceneImageUrl = computed(() => getStaticImageUrl(scene.value?.image_url))

// The scene box keeps the manifest's intrinsic aspect ratio so slot
// percentages map 1:1 onto the rendered box.
const sceneStyle = computed(() => {
  if (!scene.value) return {}
  return { aspectRatio: `${scene.value.width} / ${scene.value.height}` }
})

const fighters = computed<ArenaFighter[]>(() => arenaStore.getRoom(props.room.id)?.fighters ?? [])

const dwellerById = computed(
  () => new Map(props.assignedDwellers.map((dweller) => [dweller.id, dweller]))
)

// One sprite per manifest slot; fighters map to slots in order (A → first slot).
// Slot x/y are scene intrinsic pixels converted to percentages, with the feet
// on y — the sprite is anchored at its bottom-center and mirrored when the
// actor faces left.
const slots = computed(() => {
  const sceneValue = scene.value
  if (!sceneValue) return []
  return sceneValue.actor_slots.map((slot, index) => {
    const fighter = fighters.value[index] ?? null
    const dweller = fighter ? dwellerById.value.get(fighter.id) : undefined
    const name =
      fighter?.name ??
      (dweller ? `${dweller.first_name} ${dweller.last_name ?? ''}`.trim() : 'Fighter')
    return {
      id: slot.id,
      actor: fighter?.actor ?? null,
      portraitUrl: dweller?.thumbnail_url ?? null,
      alt: name,
      style: {
        left: `${(slot.x / sceneValue.width) * 100}%`,
        top: `${(slot.y / sceneValue.height) * 100}%`,
        width: `${ACTOR_WIDTH_PERCENT}%`,
        transform: `translate(-50%, -100%) scaleX(${slot.facing === 'left' ? -1 : 1}) scale(${slot.scale})`,
      },
    }
  })
})
</script>

<template>
  <div class="arena-room-detail">
    <section v-if="scene" class="arena-scene" :style="sceneStyle" aria-label="Arena scene">
      <img v-if="sceneImageUrl" :src="sceneImageUrl" alt="Arena" class="arena-scene__image" />
      <div
        v-for="slot in slots"
        :key="slot.id"
        class="arena-scene__slot"
        :style="slot.style"
      >
        <ArenaActorSprite
          :actor="slot.actor"
          :portrait-url="slot.portraitUrl"
          :alt="slot.alt"
        />
      </div>
    </section>
    <RoomPreviewSection
      v-else
      :room-name="room.name"
      :image-url="room.image_url ?? null"
      :room-image-url="roomImageUrl"
      :room-units="room.size ?? room.size_min ?? 3"
      :dweller-capacity="dwellerCapacity"
      :assigned-dwellers="assignedDwellers"
      :assign-enabled="false"
    />
    <ArenaModal
      :vault-id="vaultId"
      :room-id="room.id"
    />
    <RoomActions
      :room="room"
      :upgrade-info="upgradeInfo"
      :is-upgrading="isUpgrading"
      :is-destroying="isDestroying"
      :is-vault-door="isVaultDoor"
      :assigned-dweller-count="assignedDwellers.length"
      @upgrade="emit('upgrade')"
      @destroy="emit('destroy')"
      @unassign-all="emit('unassignAll')"
    />
  </div>
</template>

<style scoped>
.arena-room-detail {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.arena-scene {
  position: relative;
  width: 100%;
  overflow: hidden;
  border: 1px solid var(--color-theme-glow);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.8);
}

.arena-scene__image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.arena-scene__slot {
  position: absolute;
  transform-origin: bottom center;
}
</style>

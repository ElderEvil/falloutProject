<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { PersonStanding } from '@lucide/vue'
import { Button } from '@/core/components/ui/button'
import {
  getAbilityConfig,
  getDwellerDisplayName,
  getDwellerPortraitScale,
  type DwellerShort,
} from '@/modules/dwellers/models/dweller'
import { getStaticImageUrl } from '@/core/utils/image'
import DwellerNameBadge from '@/modules/dwellers/components/DwellerNameBadge.vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import CombatPet from '@/modules/combat/components/CombatPet.vue'

const props = withDefaults(
  defineProps<{
    dweller: DwellerShort | null
    kind?: 'worker' | 'apprentice' | 'client'
    assignEnabled?: boolean
    selectionMode?: boolean
    slotId?: string
    roomName?: string
  }>(),
  { kind: 'worker', assignEnabled: true, selectionMode: false, roomName: 'room' }
)
const emit = defineEmits<{ activate: [id: string]; unassign: [id: string]; assign: [] }>()
const name = computed(() => getDwellerDisplayName(props.dweller))
const label = computed(() => props.kind.charAt(0).toUpperCase() + props.kind.slice(1))
const stat = computed(
  () =>
    getAbilityConfig(props.dweller?.apprentice_stat)?.letter ??
    props.dweller?.apprentice_stat?.charAt(0).toUpperCase() ??
    ''
)
const teenSilhouette = getStaticImageUrl(
  '/static/dweller_images/variants/teen/FOS_Dw_Default_Human_Teen_Male_SkinBrown_HairBrown.webp'
)
const buttonLabel = computed(() => {
  if (props.selectionMode) return `Choose ${props.kind}${props.dweller ? `: ${name.value}` : ''}`
  if (props.dweller) return `Open ${props.dweller.first_name} ${props.dweller.last_name ?? ''}`
  return props.kind === 'apprentice'
    ? 'Assign child or teen apprentice to this slot'
    : `Assign ${props.kind}`
})
const unassignLabel = computed(() =>
  props.selectionMode
    ? `Unassign ${name.value} from ${props.roomName}`
    : `Unassign ${props.dweller?.first_name} ${props.dweller?.last_name ?? ''}`
)
const activate = () => {
  if (props.dweller && !props.selectionMode) emit('activate', props.dweller.id)
  else emit('assign')
}
</script>

<template>
  <div
    class="dweller-sprite-slot dweller-sprite-slot-lg shrink-0"
    role="group"
    :aria-label="`${label} slot`"
    :class="{
      'slot-filled': dweller,
      'apprentice-slot': kind === 'apprentice',
      'client-slot': kind === 'client',
      'selection-slot': selectionMode,
    }"
  >
    <div class="scene-occupant min-w-0 [&>.combat-pet]:z-2">
      <DwellerNameBadge v-if="dweller" :name="dweller.first_name" :full-name="name" />
      <span v-else-if="selectionMode" class="h-4" aria-hidden="true" />
      <!-- @vue-ignore -->
      <Button
        v-if="dweller || assignEnabled"
        type="button"
        variant="ghost"
        :id="slotId"
        class="placeholder-dweller"
        :disabled="selectionMode && !assignEnabled"
        :class="dweller ? 'scene-dweller' : ['empty scene-empty-slot', `scene-empty-${kind}`]"
        :style="dweller ? { '--dweller-body-scale': getDwellerPortraitScale(dweller) } : undefined"
        :aria-label="buttonLabel"
        @click="activate"
      >
        <DwellerPortrait
          v-if="dweller"
          :thumbnail-url="dweller.thumbnail_url"
          :alt="name"
          image-class="scene-dweller-portrait h-full w-full"
          prefer-thumbnail
          :zoom="false"
        >
          <template #fallback
            ><PersonStanding class="scene-dweller-icon text-theme-primary" aria-hidden="true"
          /></template>
        </DwellerPortrait>
        <template v-else>
          <span
            class="empty-dweller-silhouette"
            :class="{ 'empty-dweller-silhouette--apprentice': kind === 'apprentice' }"
            :style="
              kind === 'apprentice'
                ? { '--dweller-silhouette': teenSilhouette ? `url('${teenSilhouette}')` : 'none' }
                : undefined
            "
            aria-hidden="true"
          />
          <span v-if="kind !== 'apprentice'" class="empty-dweller-plus" aria-hidden="true"
            ><Icon icon="mdi:plus"
          /></span>
          <span v-if="selectionMode" class="sr-only">Add {{ kind }}</span>
        </template>
        <span
          v-if="kind === 'apprentice'"
          class="apprentice-marker"
          role="img"
          :aria-label="
            dweller ? `Apprentice training ${dweller.apprentice_stat}` : 'Apprentice slot'
          "
        >
          <Icon icon="mdi:school-outline" />{{ dweller ? stat : '+' }}
        </span>
      </Button>
      <div v-else class="placeholder-dweller empty scene-empty-slot" aria-hidden="true">
        <span class="empty-dweller-silhouette" />
      </div>
      <CombatPet
        v-if="dweller?.pet"
        :pet="dweller.pet"
        :owner-name="name"
        :owner-id="dweller.id"
        facing="right"
      />
      <span
        v-if="selectionMode || kind === 'client'"
        class="slot-role"
        :class="{ 'client-marker': kind === 'client' }"
        >{{ label }}</span
      >
      <Button
        v-if="dweller && assignEnabled"
        type="button"
        variant="ghost"
        class="scene-unassign"
        :aria-label="unassignLabel"
        @click="emit('unassign', dweller.id)"
        ><Icon icon="mdi:account-minus-outline"
      /></Button>
    </div>
  </div>
</template>

<style scoped>
.dweller-sprite-slot,
.scene-occupant {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* The preview band owns this slot's height; the slot only fills it. */
.dweller-sprite-slot {
  height: 100%;
  aspect-ratio: var(--portrait-frame-aspect, 2 / 3);
  align-items: flex-end;
}

/* The portrait frame ratio is a parent token (`--portrait-frame-aspect`, set by
   RoomPreviewSection). The slot must never establish its own width or height. */
.scene-occupant {
  flex-direction: column;
  justify-content: flex-end;
  height: 100%;
  aspect-ratio: var(--portrait-frame-aspect, 2 / 3);
  gap: 0.1rem;
}

/* The badge sits above the sprite and must not steal its height. */
.scene-occupant > * {
  flex-shrink: 0;
}

/* Keep worker and apprentice portraits the same size. */
.dweller-sprite-slot-lg .placeholder-dweller {
  width: 100%;
  height: calc(100% * var(--dweller-body-scale, 1));
}

.placeholder-dweller {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  padding: 0;
  border: 2px dashed var(--color-theme-glow);
  border-radius: 8px;
  background: var(--color-surface-sunken);
}

.placeholder-dweller.empty {
  border-color: transparent;
  background: transparent;
}

.scene-empty-slot,
.scene-dweller {
  color: inherit;
  cursor: pointer;
}

.scene-empty-slot:hover,
.scene-empty-slot:focus-visible {
  outline: 2px solid var(--color-theme-primary);
  outline-offset: 3px;
}

.scene-empty-slot:hover .empty-dweller-silhouette,
.scene-empty-slot:focus-visible .empty-dweller-silhouette {
  background-color: var(--color-theme-primary);
  opacity: 1;
  filter: drop-shadow(0 0 9px color-mix(in srgb, var(--color-theme-primary) 65%, transparent));
}

.slot-filled .placeholder-dweller {
  border-style: solid;
  border-color: var(--color-theme-primary);
  background: var(--color-surface-raised);
}

.slot-filled .placeholder-dweller.scene-dweller {
  border: 0;
  background: transparent;
}

.scene-dweller:hover,
.scene-dweller:focus-visible {
  box-shadow: 0 0 8px var(--color-theme-glow);
  outline: none;
}

.scene-unassign {
  position: absolute;
  right: -0.45rem;
  bottom: -0.4rem;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--color-danger) 70%, transparent);
  border-radius: 5px;
  background: color-mix(in srgb, var(--color-surface-sunken) 92%, black);
  color: var(--color-danger);
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--color-danger) 18%, transparent),
    0 2px 8px color-mix(in srgb, var(--color-surface-canvas) 65%, transparent);
  cursor: pointer;
  opacity: 0;
  pointer-events: none;
  transition:
    opacity 150ms ease,
    background 150ms ease,
    border-color 150ms ease,
    box-shadow 150ms ease;
}

.scene-occupant:hover .scene-unassign,
.scene-unassign:focus-visible {
  opacity: 1;
  pointer-events: auto;
}

@media (hover: none) {
  .scene-unassign {
    opacity: 1;
    pointer-events: auto;
  }
}

.scene-unassign:focus-visible,
.scene-unassign:hover {
  border-color: var(--color-danger);
  background: color-mix(in srgb, var(--color-danger) 18%, var(--color-surface-sunken));
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--color-danger) 45%, transparent),
    0 0 10px color-mix(in srgb, var(--color-danger) 45%, transparent);
  outline: 2px solid var(--color-theme-primary);
  outline-offset: 2px;
}

.scene-unassign :deep(svg) {
  width: 0.875rem;
  height: 0.875rem;
}

.scene-dweller :deep(.scene-dweller-portrait),
.scene-dweller :deep(.scene-dweller-icon) {
  width: 100%;
  height: 100%;
}

.empty-dweller-silhouette {
  display: block;
  width: 100%;
  height: 100%;
  background-color: var(--color-surface-sunken);
  -webkit-mask-image: var(--dweller-silhouette);
  mask-image: var(--dweller-silhouette);
  -webkit-mask-repeat: no-repeat;
  mask-repeat: no-repeat;
  -webkit-mask-position: center bottom;
  mask-position: center bottom;
  -webkit-mask-size: contain;
  mask-size: contain;
  -webkit-mask-mode: alpha;
  mask-mode: alpha;
  opacity: 0.78;
  filter: drop-shadow(0 0 4px color-mix(in srgb, var(--color-theme-primary) 30%, transparent));
  transition:
    background-color 150ms ease,
    opacity 150ms ease,
    filter 150ms ease;
}

.empty-dweller-silhouette--apprentice {
  opacity: 0.82;
  filter: drop-shadow(0 0 5px color-mix(in srgb, var(--badge-age-teen) 35%, transparent));
}

.scene-empty-apprentice:hover .empty-dweller-silhouette,
.scene-empty-apprentice:focus-visible .empty-dweller-silhouette {
  background-color: var(--badge-age-teen);
  opacity: 1;
  filter: drop-shadow(0 0 10px color-mix(in srgb, var(--badge-age-teen) 70%, transparent));
}

.empty-dweller-plus {
  position: absolute;
  right: 0.1rem;
  bottom: 0.1rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.15rem;
  height: 1.15rem;
  border: 1px solid var(--color-theme-primary);
  border-radius: 999px;
  background: var(--color-surface-sunken);
  color: var(--color-theme-primary);
  line-height: 0;
  pointer-events: none;
}

.empty-dweller-plus :deep(svg) {
  width: 0.7rem;
  height: 0.7rem;
}

.scene-dweller :deep(.scene-dweller-portrait) {
  width: 100%;
  height: 100%;
  max-width: 100%;
  object-fit: contain;
  object-position: center bottom;
}

.scene-dweller :deep([role='img']) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.apprentice-slot .placeholder-dweller,
.apprentice-slot .slot-filled .placeholder-dweller.scene-dweller {
  border: 0;
  background: transparent;
  box-shadow: none;
}

.apprentice-marker :deep(svg) {
  width: 0.75rem;
  height: 0.75rem;
}

.apprentice-marker {
  position: absolute;
  top: -0.35rem;
  right: -0.35rem;
  display: inline-flex;
  align-items: center;
  gap: 0.1rem;
  padding: 0.1rem 0.2rem;
  border: 1px solid var(--badge-age-teen);
  border-radius: 999px;
  background: var(--color-surface-sunken);
  color: var(--badge-age-teen);
  font-size: 0.625rem;
  font-weight: 700;
}

.selection-slot .placeholder-dweller {
  border: 0;
  background: transparent;
  color: color-mix(in srgb, var(--color-theme-primary) 50%, transparent);
}
.selection-slot .empty-dweller-silhouette {
  background-color: currentColor;
}
.selection-slot .placeholder-dweller:hover {
  color: var(--color-theme-primary);
  outline: none;
  box-shadow: none;
}
.selection-slot .placeholder-dweller:focus-visible {
  color: var(--color-theme-primary);
  outline: 2px solid var(--color-theme-primary);
  outline-offset: 3px;
}
/* Role captions hang under the silhouette so the sprite keeps the same floor
   baseline as worker/apprentice slots in production rooms. */
.slot-role {
  position: absolute;
  top: 100%;
  left: 50%;
  display: inline-flex;
  height: 1rem;
  align-items: center;
  gap: 0.15rem;
  padding: 0 0.3rem;
  border-radius: 0.3rem;
  background: color-mix(in srgb, black 70%, transparent);
  color: var(--color-theme-primary);
  font-size: 0.6rem;
  line-height: 1;
  text-transform: uppercase;
  white-space: nowrap;
  pointer-events: none;
  transform: translateX(-50%);
}
.client-marker {
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 45%, transparent);
}
</style>

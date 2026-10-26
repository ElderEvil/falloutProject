<script setup lang="ts">
import { computed } from 'vue'
import { PawPrint } from '@lucide/vue'
import { getStaticImageUrl } from '@/core/utils/image'
import { useFallbackImage } from '@/modules/rooms/composables/useFallbackImage'
import type { components } from '@/core/types/api.generated'
import CombatantMotion from './CombatantMotion.vue'
import type { PlayingCombatAction } from '../models/playback'

const props = defineProps<{
  pet: components['schemas']['CombatPet']
  ownerName: string
  facing: 'left' | 'right'
  ownerId?: string
  action?: PlayingCombatAction | null
  phase?: 'prepare' | 'impact' | null
}>()
const label = computed(() => `${props.pet.name}, ${props.ownerName}’s pet`)
const { url, onError } = useFallbackImage(() => [getStaticImageUrl(props.pet.image_url)])
</script>

<template>
  <div
    class="combat-pet pointer-events-none absolute bottom-0 z-10 aspect-[3/2] h-[35%]"
    :class="facing === 'left' ? 'right-0' : 'left-0'"
  >
    <CombatantMotion
      class="actor-ground-shadow"
      :fighter-id="ownerId ?? ''"
      :facing="facing"
      :action="action"
      :phase="phase"
      companion
    >
      <img
        v-if="url"
        :src="url"
        :alt="label"
        class="size-full object-contain object-bottom drop-shadow-lg"
        :class="{ '-scale-x-100': facing === 'left' }"
        @error="onError"
      />
      <PawPrint
        v-else
        role="img"
        :aria-label="label"
        class="size-full text-theme-primary/70"
        :class="{ '-scale-x-100': facing === 'left' }"
      />
    </CombatantMotion>
  </div>
</template>

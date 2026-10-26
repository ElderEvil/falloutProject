<script setup lang="ts">
import { computed, watch } from 'vue'
import ArenaRing from '@/modules/rooms/components/ArenaRing.vue'
import { useCombatPlayback } from '@/modules/combat/composables/useCombatPlayback'
import { WASTELAND_SCENES } from '../models/wastelandScenes'
import type { SiteRoomView } from '../api/expeditionSite'

const props = defineProps<{
  room: SiteRoomView
  running: boolean
  loading: boolean
  wide?: boolean
}>()
const emit = defineEmits<{ playing: [value: boolean]; skill: [] }>()
const combat = computed(() => props.room.combat_state!)
const playback = useCombatPlayback(() => ({
  key: `${props.room.exploration_id}:${props.room.site_id}`,
  health: Object.fromEntries(combat.value.fighters.map((fighter) => [fighter.id, fighter.health])),
  events: combat.value.events ?? [],
}))
watch(playback.isPlaying, (value) => emit('playing', value), { immediate: true })
const artwork = computed(() =>
  props.room.scene_id ? WASTELAND_SCENES[props.room.scene_id].battleback : null
)
const landscape = computed(() =>
  props.wide && props.room.scene_id ? WASTELAND_SCENES[props.room.scene_id].landscape : null
)
const fighters = computed(() =>
  combat.value.fighters.map((fighter) => ({
    ...fighter,
    health: playback.health.value[fighter.id] ?? fighter.health,
  }))
)
const ring = computed(() => ({
  team_a: fighters.value.slice(0, 1),
  team_b: fighters.value.slice(1),
  mode: 'hunt',
  match_done: props.room.status !== 'in_room' && !playback.isPlaying.value,
  countdown_remaining: 0,
  fight_started: props.running,
  next_attack_team: combat.value.next_attack_team ?? ('A' as const),
}))
const emptySkills = new Set<string>()
</script>

<template>
  <div :class="wide ? 'flex h-full min-h-0 flex-col' : undefined">
    <div
      :class="wide ? 'relative min-h-0 flex-1 [container-type:size]' : undefined"
      aria-label="Battlefield space"
    >
      <ArenaRing
        :class="
          wide
            ? 'absolute top-1/2 left-1/2 w-[min(100cqw,calc(100cqh*50/37))] -translate-x-1/2 -translate-y-1/2 lg:w-[min(100cqw,calc(100cqh*16/9))]'
            : undefined
        "
        :state="ring"
        :scene-image-url="artwork?.variants[1]?.src"
        :scene-srcset="artwork?.variants.map((image) => `${image.src} ${image.width}w`).join(', ')"
        :wide-scene-image-url="landscape?.variants[1]?.src"
        :wide-scene-srcset="
          landscape?.variants.map((image) => `${image.src} ${image.width}w`).join(', ')
        "
        encounter
        :contained="wide"
        :heading="room.site_name"
        team-a-label="DWELLER"
        team-b-label="HOSTILES"
        :status-label="
          playback.isPlaying.value
            ? 'ENGAGED'
            : room.status === 'defeated'
              ? 'ESCAPED'
              : room.status === 'cleared'
                ? 'AREA SECURED'
                : running
                  ? 'ENGAGED'
                  : 'READY'
        "
        :skill-enabled="
          running &&
          !loading &&
          !playback.isPlaying.value &&
          ring.next_attack_team === 'A' &&
          room.status === 'in_room'
        "
        :pending-skills="emptySkills"
        :attacking-team="null"
        :attacking-fighter-id="playback.active.value?.action.actor_id"
        :active-action="playback.active.value"
        :combat-phase="playback.phase.value"
        :damage-numbers="playback.damageNumbers.value"
        @skill="emit('skill')"
      />
    </div>
    <p v-if="!wide" class="mt-3 text-sm leading-relaxed text-theme-primary/80">{{ room.flavor }}</p>
  </div>
</template>

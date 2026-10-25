<script setup lang="ts">
import { computed } from 'vue'
import CombatEffect from './CombatEffect.vue'
import type { PlayingCombatAction } from '../models/playback'

const props = defineProps<{
  fighterId: string
  facing?: 'left' | 'right'
  action?: PlayingCombatAction | null
  phase?: 'prepare' | 'impact' | null
}>()

const attacking = computed(() => props.action?.action.actor_id === props.fighterId)
const target = computed(() =>
  props.action?.action.targets.find((impact) => impact.target_id === props.fighterId)
)
const hit = computed(() => props.phase === 'impact' && !!target.value)
const body = computed(() =>
  attacking.value ? (props.action?.action.actor_body ?? 'human') : (target.value?.body ?? 'human')
)
const effect = computed(() => props.action?.action.effect ?? 'strike')
const melee = computed(() => ['strike', 'punch', 'thrust', 'sweep'].includes(effect.value))
const metal = computed(() => ['synth', 'power-armor'].includes(body.value))
const active = computed(() => !!props.action && (attacking.value || hit.value))
</script>

<template>
  <div class="combatant-motion relative flex size-full items-end justify-center">
    <div
      :key="active ? `${action?.id}:${phase}` : 'idle'"
      class="combat-body flex size-full items-end justify-center"
      :class="[
        `combat-body--${body}`,
        {
          'combat-body--left': facing === 'left',
          'combat-body--windup': attacking && phase === 'prepare' && melee,
          'combat-body--brace': attacking && phase === 'prepare' && !melee,
          'combat-body--attack': attacking && phase === 'impact' && melee,
          'combat-body--recoil': attacking && phase === 'impact' && !melee,
          'combat-body--hit': hit,
          'combat-body--skill': !!action?.action.skill,
          'combat-body--stationary': !!action?.accelerated,
        },
      ]"
    >
      <slot />
    </div>
    <CombatEffect
      v-if="active"
      :key="`${action?.id}:${phase}`"
      :effect="effect"
      :preparing="phase === 'prepare'"
      :skill="!!action?.action.skill"
      :metal="hit && metal"
      :facing="attacking ? facing : facing === 'left' ? 'right' : 'left'"
    />
  </div>
</template>

<style scoped>
.combat-body {
  --travel: 10px;
  --recoil: 4px;
  --lean: 4deg;
  --direction: 1;
  transform-origin: center bottom;
  animation-duration: 200ms;
  animation-fill-mode: both;
  animation-timing-function: ease-out;
}
.combat-body--left {
  --direction: -1;
}
.combat-body--ghoul {
  --lean: 6deg;
  --travel: 8px;
}
.combat-body--feral {
  --lean: 9deg;
  --travel: 12px;
  animation-timing-function: steps(3, end);
}
.combat-body--mutant {
  --lean: 3deg;
  --travel: 7px;
  --recoil: 2px;
}
.combat-body--behemoth {
  --lean: 2deg;
  --travel: 5px;
  --recoil: 1px;
}
.combat-body--synth {
  --lean: 1deg;
  --travel: 8px;
  animation-timing-function: cubic-bezier(0.2, 0, 0.2, 1);
}
.combat-body--power-armor {
  --lean: 2deg;
  --travel: 5px;
  --recoil: 1px;
}
.combat-body--windup {
  animation-name: combat-windup;
  animation-duration: 150ms;
}
.combat-body--brace {
  animation-name: combat-brace;
  animation-duration: 150ms;
}
.combat-body--attack {
  animation-name: combat-strike;
}
.combat-body--recoil {
  animation-name: combat-recoil;
}
.combat-body--hit {
  animation-name: combat-hit;
}
.combat-body--skill {
  animation-duration: 300ms;
}
.combat-body--skill.combat-body--windup,
.combat-body--skill.combat-body--brace {
  animation-duration: 250ms;
}
.combat-body--stationary {
  animation: none;
}
@keyframes combat-windup {
  to {
    transform: translateX(calc(var(--direction) * -2px))
      rotate(calc(var(--direction) * var(--lean) * -1));
  }
}
@keyframes combat-brace {
  to {
    transform: rotate(calc(var(--direction) * var(--lean) * 0.4));
  }
}
@keyframes combat-strike {
  0%,
  25% {
    transform: translateX(calc(var(--direction) * var(--travel)))
      rotate(calc(var(--direction) * var(--lean)));
  }
  100% {
    transform: none;
  }
}
@keyframes combat-recoil {
  from {
    transform: translateX(calc(var(--direction) * var(--recoil) * -1))
      rotate(calc(var(--direction) * var(--lean) * -0.5));
  }
  to {
    transform: none;
  }
}
@keyframes combat-hit {
  from {
    transform: translateX(calc(var(--direction) * var(--recoil) * -1))
      rotate(calc(var(--direction) * var(--lean) * -1));
    filter: brightness(1.7);
  }
  to {
    transform: none;
    filter: none;
  }
}
@media (prefers-reduced-motion: reduce) {
  .combat-body {
    animation: none;
  }
}
</style>

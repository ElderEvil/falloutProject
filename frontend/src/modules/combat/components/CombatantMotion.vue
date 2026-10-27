<script setup lang="ts">
import { computed } from 'vue'
import CombatEffect from './CombatEffect.vue'
import type { PlayingCombatAction } from '../models/playback'

const props = defineProps<{
  fighterId: string
  facing?: 'left' | 'right'
  action?: PlayingCombatAction | null
  phase?: 'prepare' | 'impact' | null
  companion?: boolean
}>()

const attacking = computed(() => props.action?.action.actor_id === props.fighterId)
const target = computed(() =>
  props.companion
    ? undefined
    : props.action?.action.targets.find((impact) => impact.target_id === props.fighterId)
)
const hit = computed(() => props.phase === 'impact' && !!target.value)
const body = computed(() =>
  props.companion
    ? 'human'
    : attacking.value
      ? (props.action?.action.actor_body ?? 'human')
      : (target.value?.body ?? 'human')
)
const effect = computed(() =>
  props.companion ? 'strike' : (props.action?.action.effect ?? 'strike')
)
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
          'combat-body--damaged': hit && (target?.damage ?? 0) > 0,
          'combat-body--skill': !companion && !!action?.action.skill,
          'combat-body--stationary': !!action?.accelerated,
        },
      ]"
    >
      <slot />
    </div>
    <div
      v-if="hit && action?.action.skill && !companion"
      class="skill-hit pointer-events-none absolute inset-0 z-20"
      :class="{
        'skill-hit--stationary': action.accelerated,
        'skill-hit--explosion': action.action.skill_icon === 'heavy-explosive',
        'skill-hit--energy': action.action.skill_icon?.startsWith('energy-'),
        'skill-hit--heat': action.action.skill_icon === 'heavy-flamer',
        'skill-hit--scatter': action.action.skill_icon === 'gun-shotgun',
        'skill-hit--hammer': action.action.skill_icon === 'melee-blunt',
        'skill-hit--automatic': action.action.skill_icon === 'heavy-automatic',
      }"
      aria-hidden="true"
    />
    <CombatEffect
      v-if="active && !companion"
      :key="`${action?.id}:${phase}`"
      :class="attacking ? (facing === 'left' ? 'effect-forward-left' : 'effect-forward-right') : ''"
      :effect="effect"
      :preparing="phase === 'prepare'"
      :skill="!!action?.action.skill"
      :metal="hit && metal"
      :facing="attacking ? facing : facing === 'left' ? 'right' : 'left'"
    />
  </div>
</template>

<style scoped>
.effect-forward-right {
  translate: 50% 0;
}
.effect-forward-left {
  translate: -50% 0;
}
.skill-hit {
  background: url('/assets/combat/skill-hit.webp') 0 0 / 1600% 100% no-repeat;
  animation: skill-hit 300ms steps(15, end) both;
}
.skill-hit--explosion {
  background-image: url('/assets/combat/skill-explosion.webp');
}
.skill-hit--energy {
  filter: hue-rotate(150deg);
}
.skill-hit--heat {
  background: radial-gradient(
    ellipse,
    transparent 25%,
    var(--color-warning) 30%,
    transparent 35%,
    transparent 46%,
    var(--color-danger) 50%,
    transparent 56%
  );
  animation: skill-wave 300ms ease-out both;
}
.skill-hit--scatter {
  background: repeating-conic-gradient(var(--color-warning) 0deg 4deg, transparent 4deg 30deg);
  mask-image: radial-gradient(ellipse, transparent 12%, black 25%, transparent 70%);
  animation: skill-wave 300ms ease-out both;
}
@keyframes skill-wave {
  from {
    transform: scale(0.45);
    opacity: 1;
  }
  to {
    transform: scale(1.15);
    opacity: 0;
  }
}
.skill-hit--hammer::after {
  content: '';
  position: absolute;
  inset: 38% 4%;
  border: 3px solid var(--color-warning);
  border-radius: 50%;
  animation: skill-wave 300ms ease-out both;
}
.skill-hit--automatic {
  background: repeating-linear-gradient(
    165deg,
    transparent 0 14%,
    var(--color-warning) 15% 17%,
    transparent 18% 28%
  );
  mask-image: radial-gradient(ellipse, black, transparent 70%);
  animation: skill-wave 300ms ease-out both;
}
.skill-hit--stationary::after {
  animation: none;
}
.skill-hit--stationary {
  animation: none;
  background-position: 26.6667% 0;
}
@keyframes skill-hit {
  to {
    background-position: 100% 0;
  }
}
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
.combat-body--damaged {
  filter: drop-shadow(0 0 3px var(--color-danger)) drop-shadow(0 0 5px var(--color-danger));
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
  }
  to {
    transform: none;
  }
}
@media (prefers-reduced-motion: reduce) {
  .combat-body {
    animation: none;
  }
  .skill-hit--hammer::after {
    animation: none;
  }
  .skill-hit {
    animation: none;
    background-position: 26.6667% 0;
  }
}
</style>

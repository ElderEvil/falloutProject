<script setup lang="ts">
import { onScopeDispose, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Button } from '@/core/components/ui/button'
import { Switch } from '@/core/components/ui/switch'
import { useSound } from '@/core/composables/useSound'
import ArenaRing from '@/modules/rooms/components/ArenaRing.vue'
import type { ArenaFighter } from '@/modules/rooms/api/arena'
import type { CombatEffect, CombatSkillIcon, PlayingCombatAction } from '../models/playback'

const fighter = (id: string, name: string, thumbnail: string): ArenaFighter => ({
  id,
  name,
  level: 10,
  health: 80,
  max_health: 100,
  power: 10,
  is_creature: false,
  is_robot: false,
  thumbnail_url: thumbnail,
})
const state = {
  team_a: [
    fighter(
      'attacker',
      'Attacker',
      '/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Female.webp'
    ),
  ],
  team_b: [
    fighter('target', 'Target', '/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Male.webp'),
  ],
  match_done: false,
  fight_started: true,
  next_attack_team: 'A' as const,
}
const skills: Array<{ name: string; icon: CombatSkillIcon; effect: CombatEffect }> = [
  { name: 'Haymaker', icon: 'unarmed', effect: 'punch' },
  { name: 'Crushing Blow', icon: 'melee-blunt', effect: 'strike' },
  { name: 'Cleave', icon: 'melee-edged', effect: 'sweep' },
  { name: 'Piercing Strike', icon: 'melee-pointed', effect: 'thrust' },
  { name: 'Quick Draw', icon: 'gun-pistol', effect: 'shot' },
  { name: 'Aimed Shot', icon: 'gun-rifle', effect: 'shot' },
  { name: 'Scattershot', icon: 'gun-shotgun', effect: 'burst' },
  { name: 'Overcharge', icon: 'energy-pistol', effect: 'beam' },
  { name: 'Beam Sweep', icon: 'energy-rifle', effect: 'beam' },
  { name: 'Full Auto', icon: 'heavy-automatic', effect: 'burst' },
  { name: 'Firestorm', icon: 'heavy-flamer', effect: 'flame' },
  { name: 'Blast Wave', icon: 'heavy-explosive', effect: 'blast' },
]
const selectedSkill = ref('gun-rifle')
const { playSound } = useSound()
const still = ref(false)
const action = ref<PlayingCombatAction | null>(null)
const phase = ref<'prepare' | 'impact' | null>(null)
let timer: ReturnType<typeof setTimeout> | undefined
let sequence = 0

function play(): void {
  clearTimeout(timer)
  const skill = skills.find((item) => item.icon === selectedSkill.value)!
  action.value = {
    id: String(++sequence),
    message: skill.name,
    accelerated: still.value,
    action: {
      actor_id: 'attacker',
      actor_body: 'human',
      effect: skill.effect,
      skill: skill.name,
      skill_icon: skill.icon,
      targets: [{ target_id: 'target', body: 'human', damage: 10 }],
    },
  }
  phase.value = still.value ? 'impact' : 'prepare'
  if (still.value) playSound('arenaSkill', 'sfx')
  if (!still.value) {
    timer = setTimeout(() => {
      phase.value = 'impact'
      if (action.value) playSound('arenaSkill', 'sfx')
      timer = setTimeout(() => {
        phase.value = null
        action.value = null
      }, 300)
    }, 250)
  }
}
onScopeDispose(() => clearTimeout(timer))
</script>

<template>
  <main class="mx-auto flex max-w-4xl flex-col gap-6 p-4 font-mono text-theme-primary sm:py-8">
    <header class="flex flex-col gap-3 border-b border-theme-primary/30 pb-4">
      <RouterLink to="/dev" class="w-fit text-sm underline underline-offset-4"
        >Back to development tools</RouterLink
      >
      <h1 class="text-2xl font-bold">Skill effects</h1>
      <p class="max-w-2xl text-sm text-theme-primary/80">
        Play a skill to see the impact on the target. Your system's reduced-motion setting is
        respected.
      </p>
      <label class="flex max-w-sm flex-col gap-2 text-sm">
        Weapon skill
        <select
          v-model="selectedSkill"
          class="rounded-md border border-theme-primary/40 bg-surface px-3 py-2 text-theme-primary"
        >
          <option v-for="skill in skills" :key="skill.icon" :value="skill.icon">
            {{ skill.name }}
          </option>
        </select>
      </label>
      <label class="flex w-fit items-center gap-2 text-sm">
        <Switch v-model:checked="still" aria-label="Hold impact frame" />
        Hold impact frame
      </label>
      <Button class="w-fit" @click="play">Play skill</Button>
    </header>
    <div class="aspect-[50/37] w-full sm:aspect-video">
      <ArenaRing
        class="h-full"
        :state="state"
        scene-image-url="/assets/room-scenes/arena-cartoon-tier-3-v1.webp"
        :skill-enabled="false"
        :active-action="action"
        :combat-phase="phase"
        :damage-numbers="[]"
      />
    </div>
  </main>
</template>

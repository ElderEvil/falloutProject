<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'
import type { VisualAttributes } from '../models/dweller'

interface Props {
  visualAttributes?: VisualAttributes | null
  compact?: boolean
}

interface IdentitySignal {
  icon?: string
  monogram?: string
  label: string
  value: string
}

const props = withDefaults(defineProps<Props>(), { compact: false })

const IDENTITY_CONFIG: Record<string, Omit<IdentitySignal, 'value'>> = {
  human: { icon: 'mdi:account', label: 'Human' },
  ghoul: { icon: 'mdi:radioactive', label: 'Ghoul' },
  super_mutant: { icon: 'mdi:arm-flex', label: 'Super Mutant' },
  synth: { icon: 'mdi:robot-outline', label: 'Synth' },
  vault_dweller: { icon: 'mdi:shield-home', label: 'Vault Dweller' },
  brotherhood_of_steel: { icon: 'mdi:shield-sword', label: 'Brotherhood of Steel' },
  enclave: { icon: 'mdi:shield-star', label: 'Enclave' },
  minutemen: { icon: 'mdi:crosshairs-gps', label: 'Minutemen' },
  raiders: { icon: 'mdi:skull-crossbones-outline', label: 'Raiders' },
  super_mutant_tribe: { icon: 'mdi:account-group', label: 'Super Mutant Tribe' },
  children_of_atom: { icon: 'mdi:atom', label: 'Children of Atom' },
  the_institute: { icon: 'mdi:flask-outline', label: 'The Institute' },
  railroad: { icon: 'mdi:train', label: 'Railroad' },
  ncr: { icon: 'mdi:star-four-points-outline', label: 'NCR' },
  caesars_legion: { icon: 'mdi:shield-sun-outline', label: "Caesar's Legion" },
  none: { icon: 'mdi:account-question-outline', label: 'Unaffiliated' },
  sane: { icon: 'mdi:head-heart-outline', label: 'Sane' },
  wild: { icon: 'mdi:head-alert-outline', label: 'Wild' },
  feral: { icon: 'mdi:skull-outline', label: 'Feral' },
  // Ordered tiers carry a numeral instead of an icon: there is no glyph that
  // reads as "how mutated", so the icons repeated and told the player nothing.
  // Synth generations keep the robot glyph — it says "machine" — and the label
  // carries the generation. Qualitative states (ghoul sane/wild/feral) keep
  // their icons, since they are not a ladder.
  gen_1: { icon: 'mdi:robot-outline', label: 'Gen I' },
  gen_2: { icon: 'mdi:robot-outline', label: 'Gen II' },
  gen_3: { icon: 'mdi:robot-outline', label: 'Gen III' },
  mild: { monogram: 'I', label: 'Mild Mutation' },
  average: { monogram: 'II', label: 'Average Mutation' },
  behemoth: { monogram: 'III', label: 'Behemoth' },
}

const formatLabel = (value: string) =>
  value
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')

const identitySignals = computed<IdentitySignal[]>(() => {
  const attributes = props.visualAttributes
  if (!attributes) return []

  return [attributes.race, attributes.faction, attributes.state_of_being]
    .filter((value): value is NonNullable<typeof value> => value != null)
    .map((value) => ({
      ...IDENTITY_CONFIG[value],
      value: IDENTITY_CONFIG[value]?.label ?? formatLabel(value),
    }))
})
</script>

<template>
  <div
    v-if="identitySignals.length"
    class="flex flex-wrap items-center gap-1.5"
    aria-label="Dweller identity"
  >
    <UTooltip
      v-for="signal in identitySignals"
      :key="signal.value"
      :text="signal.value"
      position="top"
    >
      <div
        class="flex items-center gap-1.5 rounded-sm border border-theme-primary/40 bg-surface-sunken/70 px-2 py-1 font-mono text-xs text-theme-primary transition-colors hover:border-theme-primary hover:bg-theme-primary/10"
      >
        <Icon
          v-if="signal.icon"
          :icon="signal.icon"
          class="h-3.5 w-3.5 shrink-0 text-theme-primary"
          :ariaHidden="true"
        />
        <span
          v-else
          class="w-4 shrink-0 text-center font-mono text-[0.65rem] font-bold leading-none tracking-tight"
          aria-hidden="true"
          >{{ signal.monogram }}</span
        >
        <span v-if="!compact" class="whitespace-nowrap">{{ signal.label }}</span>
      </div>
    </UTooltip>
  </div>
</template>

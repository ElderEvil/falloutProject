<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useFeatureFlagsStore } from '../stores/featureFlags'
import DwellerBadge from './DwellerBadge.vue'
import { formatIdentityLabel, RACE_CONFIG_MAP, type VisualAttributes } from '../models/dweller'

interface Props {
  visualAttributes?: VisualAttributes | null
  compact?: boolean
  hideRace?: boolean
}

interface IdentitySignal {
  icon?: string
  monogram?: string
  marker?: { icon?: string; monogram?: string; label: string }
  label: string
}

type IdentityMetadata = Omit<IdentitySignal, 'marker'>

const props = withDefaults(defineProps<Props>(), { compact: false, hideRace: false })

const featureFlags = useFeatureFlagsStore()

onMounted(() => {
  void featureFlags.fetchFlags()
})

const IDENTITY_CONFIG: Record<string, IdentityMetadata> = {
  ...RACE_CONFIG_MAP,
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
  // Synth generations use Roman numerals; other states use a state-specific glyph.
  gen_1: { monogram: 'I', label: 'Gen I' },
  gen_2: { monogram: 'II', label: 'Gen II' },
  gen_3: { monogram: 'III', label: 'Gen III' },
  mild: { icon: 'mdi:circle-outline', label: 'Mild Mutation' },
  average: { icon: 'mdi:circle-slice-4', label: 'Average Mutation' },
  behemoth: { icon: 'mdi:arm-flex', label: 'Behemoth' },
}

const getIdentitySignal = (value: string): IdentityMetadata => {
  const meta = IDENTITY_CONFIG[value]
  return {
    icon: meta?.icon,
    monogram: meta?.monogram,
    label: meta?.label ?? formatIdentityLabel(value),
  }
}

const identitySignals = computed<IdentitySignal[]>(() => {
  const attributes = props.visualAttributes
  if (!attributes) return []

  const raceValue = props.hideRace ? undefined : attributes.race
  const stateValue = attributes.state_of_being
  const signals: IdentitySignal[] = []

  if (raceValue) {
    const race = getIdentitySignal(raceValue)
    signals.push({
      ...race,
      marker: stateValue ? getIdentitySignal(stateValue) : undefined,
    })
  }

  const otherValues = [
    featureFlags.factionMechanics ? attributes.faction : undefined,
    !raceValue ? stateValue : undefined,
  ]

  signals.push(
    ...otherValues
      .filter((value): value is NonNullable<typeof value> => value != null)
      .map(getIdentitySignal)
  )

  return signals
})
</script>

<template>
  <div
    v-if="identitySignals.length"
    class="flex flex-wrap items-center gap-1.5"
    aria-label="Dweller identity"
  >
    <DwellerBadge
      v-for="signal in identitySignals"
      :key="signal.label"
      :icon="signal.icon"
      :monogram="signal.monogram"
      :marker="signal.marker"
      color="var(--color-theme-primary)"
      :label="signal.label"
      :show-label="!compact"
      :size="compact ? 'sm' : 'md'"
    />
  </div>
</template>

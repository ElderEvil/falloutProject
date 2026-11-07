<template>
  <Card
    class="relationship-card relationship-record--grid h-full min-h-96 gap-0 rounded-lg border-2 border-theme-primary/20 p-4 shadow-none ring-0"
  >
    <div class="flex flex-col gap-3">
      <div class="grid min-w-0 grid-cols-1 items-stretch gap-2 sm:grid-cols-2">
        <RelationshipDweller :dweller="dweller1" @select="emit('select-dweller', $event)" />
        <RelationshipDweller :dweller="dweller2" @select="emit('select-dweller', $event)" />
      </div>
      <div class="flex items-center justify-center gap-2 text-theme-primary/70">
        <span class="h-px flex-1 bg-theme-primary/15" aria-hidden="true" />
        <Icon
          icon="mdi:heart"
          class="h-4 w-4 [filter:drop-shadow(0_0_4px_var(--color-theme-glow))]"
        />
        <Badge
          :variant="badgeVariant"
          class="relationship-badge text-[0.625rem]"
          :class="badgeClass"
        >
          <Icon
            v-if="relationship.relationship_type === 'MARRIED'"
            icon="mdi:heart"
            class="h-3.5 w-3.5"
          />
          {{
            RELATIONSHIP_TYPE_LABEL[relationship.relationship_type] ??
            relationship.relationship_type
          }}
        </Badge>
        <span class="h-px flex-1 bg-theme-primary/15" aria-hidden="true" />
      </div>
      <div class="rounded border border-theme-primary/20 bg-surface-sunken p-3">
        <div class="flex items-center justify-between gap-2 text-xs">
          <span class="font-bold tracking-[0.08em] text-theme-primary/60">{{ affinityLabel }}</span>
          <span
            class="font-bold"
            :class="relationship.affinity < 0 ? 'text-danger' : 'text-theme-primary'"
            >{{ relationship.affinity }}/100</span
          >
        </div>
        <Progress
          :model-value="Math.abs(relationship.affinity)"
          :tone="relationship.affinity < 0 ? 'danger' : 'default'"
          :label="affinityLabel"
          :value-text="`${Math.abs(relationship.affinity)} of 100`"
          class="mt-2 h-2"
        />
        <div
          v-if="relationship.bond_change_per_tick !== undefined"
          class="mt-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-xs"
        >
          <span
            v-if="relationship.bond_change_per_tick > 0"
            class="flex items-center gap-1 text-theme-primary/80"
          >
            <Icon icon="mdi:heart-pulse" class="h-3.5 w-3.5" :ariaHidden="true" />
            Growing closer
          </span>
          <span
            v-else-if="relationship.bond_change_per_tick < 0"
            class="flex items-center gap-1 text-warning"
          >
            <Icon icon="mdi:heart-broken" class="h-3.5 w-3.5" :ariaHidden="true" />
            Drifting apart
          </span>
          <span v-else-if="relationship.affinity >= 100" class="text-theme-primary/70"
            >Bond at full strength</span
          >
          <span v-else class="text-theme-primary/60">Bond resting · meet in Living Quarters</span>
          <span
            v-if="bondChangeLabel"
            class="font-bold"
            :class="relationship.bond_change_per_tick < 0 ? 'text-warning' : 'text-theme-primary'"
          >
            {{ bondChangeLabel }}
          </span>
        </div>
        <div
          v-if="bondFactors.length"
          class="mt-2 flex flex-wrap items-center gap-1.5 text-[0.65rem] font-bold uppercase tracking-[0.08em] text-theme-primary/55"
        >
          <span
            v-for="factor in bondFactors"
            :key="factor"
            class="rounded border border-theme-primary/20 px-1.5 py-0.5"
          >
            {{ factor }}
          </span>
        </div>
        <p v-if="nextMilestone" class="mt-2 text-xs leading-4 text-theme-primary/60">
          {{ nextMilestone }}
        </p>
      </div>
    </div>
    <div
      v-if="isPartnerLinked"
      class="mt-auto flex flex-wrap items-center gap-1.5 border-t border-theme-primary/15 pt-2"
    >
      <span class="text-[0.65rem] font-bold uppercase tracking-[0.1em] text-theme-primary/55"
        >GEN {{ generation }}</span
      >
      <span
        class="flex items-center gap-1 text-[0.65rem] font-bold uppercase tracking-[0.1em] text-theme-primary/55"
      >
        <Icon icon="mdi:human-child" class="h-3.5 w-3.5" />
        Children<template v-if="children.length"> ({{ children.length }})</template>
      </span>
      <span
        v-if="pregnancy"
        class="flex items-center gap-1 rounded border px-1.5 py-0.5 text-[0.65rem] font-bold uppercase tracking-[0.1em]"
        :class="
          pregnancy.is_due
            ? 'animate-pulse motion-reduce:animate-none border-warning/50 text-warning'
            : 'border-theme-primary/30 text-theme-primary/70'
        "
      >
        <Icon icon="mdi:baby-carriage" class="h-3.5 w-3.5" />
        {{ pregnancy.is_due ? 'Due!' : 'Expecting' }}
      </span>
      <template v-if="children.length">
        <ChildChip
          v-for="child in visibleChildren"
          :key="child.id"
          :dweller="child"
          @select="emit('select-dweller', $event)"
        />
        <button
          v-if="hiddenChildCount"
          type="button"
          class="inline-flex items-center rounded-full border border-dashed border-theme-primary/30 px-2 py-1 text-xs text-theme-primary/70 transition-colors hover:border-theme-primary/60 hover:text-theme-primary focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
          :aria-label="`Show ${children.length} children, starting with ${children[CHILD_PREVIEW_LIMIT].first_name}`"
          @click="emit('select-dweller', children[CHILD_PREVIEW_LIMIT].id)"
        >
          +{{ hiddenChildCount }} more
        </button>
      </template>
      <span v-else class="text-xs text-theme-primary/40">No children yet</span>
      <span v-if="familyPotentialLabel" class="text-xs text-theme-primary/60">
        {{ familyPotentialLabel }}
      </span>
    </div>
    <div
      v-else-if="familyPotentialLabel"
      class="mt-auto flex items-start gap-2 border-t border-theme-primary/15 pt-2 text-xs text-theme-primary/70"
    >
      <Icon
        :icon="familyPotentialIcon"
        class="h-4 w-4 shrink-0"
        :ariaHidden="true"
      />
      <div>
        <p class="font-bold text-theme-primary/80">{{ familyPotentialLabel }}</p>
        <p
          v-if="relationship.conception_potential === 'possible'"
          class="mt-1 text-theme-primary/55"
        >
          Partnership, Living Quarters and vault space needed
        </p>
      </div>
    </div>
    <div v-if="hasActions" class="flex flex-wrap justify-end gap-2 pt-3">
      <Button
        v-if="relationship.relationship_type === 'acquaintance' && relationship.affinity >= 70"
        variant="default"
        size="sm"
        class="border-2 border-theme-primary hover:shadow-glow-md"
        @click="$emit('initiate-romance')"
      >
        Romance
      </Button>
      <Button
        v-if="relationship.relationship_type === 'romantic'"
        variant="default"
        size="sm"
        class="border-2 border-theme-primary hover:shadow-glow-md"
        :disabled="relationship.can_make_partners === false"
        :title="
          relationship.can_make_partners === false
            ? 'Already committed to another dweller'
            : undefined
        "
        @click="$emit('make-partners')"
      >
        Partner
      </Button>
      <Button
        v-if="relationship.relationship_type === 'partner' && relationship.affinity >= 85"
        variant="default"
        size="sm"
        class="border-2 border-theme-primary hover:shadow-glow-md"
        @click="$emit('marry')"
      >
        Marry
      </Button>
      <Button
        v-if="isRelationshipType(relationship.relationship_type, COMMITTED_RELATIONSHIP_TYPES)"
        variant="destructive"
        size="sm"
        class="border-2 border-danger bg-transparent"
        @click="$emit('break-up')"
      >
        Break Up
      </Button>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import {
  COMMITTED_RELATIONSHIP_TYPES,
  isRelationshipType,
  PARTNER_LINKED_RELATIONSHIP_TYPES,
  RELATIONSHIP_TYPE_LABEL,
  RELATIONSHIP_TYPE_VARIANT,
  type Relationship,
} from '../../models/relationship'
import { useRelationshipMilestone } from '../../composables/useRelationshipMilestone'
import type { Pregnancy } from '../../models/pregnancy'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import RelationshipDweller from './RelationshipDweller.vue'
import ChildChip from './ChildChip.vue'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import { Card } from '@/core/components/ui/card'
import { Progress } from '@/core/components/ui/progress'

interface Props {
  relationship: Relationship
  dweller1: DwellerShort
  dweller2: DwellerShort
  children?: DwellerShort[]
  pregnancy?: Pregnancy | null
  generation?: number
}

const props = withDefaults(defineProps<Props>(), {
  children: () => [],
  pregnancy: null,
  generation: 1,
})

const emit = defineEmits<{
  'initiate-romance': []
  'make-partners': []
  marry: []
  'break-up': []
  'select-dweller': [dwellerId: string]
}>()

/** Preview a few children in the family strip, with access to the rest. */
const CHILD_PREVIEW_LIMIT = 3
const visibleChildren = computed(() => props.children.slice(0, CHILD_PREVIEW_LIMIT))
const hiddenChildCount = computed(() => Math.max(0, props.children.length - CHILD_PREVIEW_LIMIT))

/** shadcn Badge variant for the relationship type (previous badge names mapped). */
const badgeVariant = computed((): 'default' | 'secondary' | 'destructive' | 'outline' => {
  const map: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
    success: 'default',
    warning: 'outline',
    danger: 'destructive',
    info: 'outline',
    default: 'secondary',
    primary: 'default',
    secondary: 'secondary',
    outline: 'outline',
  }
  return (
    map[RELATIONSHIP_TYPE_VARIANT[props.relationship.relationship_type] ?? 'success'] ?? 'secondary'
  )
})

// No shadcn amber equivalent for `warning`; preserve its colour explicitly.
const badgeClass = computed(() => {
  const v = RELATIONSHIP_TYPE_VARIANT[props.relationship.relationship_type] ?? 'success'
  return v === 'warning' ? 'bg-warning text-black border-warning' : ''
})

/** Whether the relationship type counts as a committed partner link. */
const isPartnerLinked = computed(() =>
  isRelationshipType(props.relationship.relationship_type, PARTNER_LINKED_RELATIONSHIP_TYPES)
)

const hasActions = computed(
  () =>
    (props.relationship.relationship_type === 'acquaintance' &&
      props.relationship.affinity >= 70) ||
    isRelationshipType(props.relationship.relationship_type, COMMITTED_RELATIONSHIP_TYPES)
)

const familyPotentialIcon = computed(() => {
  switch (props.relationship.relationship_type) {
    case 'ex':
      return 'mdi:heart-broken'
    case 'rival':
      return 'mdi:sword-cross'
    default:
      return 'mdi:human-child'
  }
})

const familyPotentialLabel = computed(() => {
  if (props.relationship.relationship_type === 'rival') return 'Rivals'
  if (props.relationship.relationship_type === 'ex') return 'Former couple'
  switch (props.relationship.conception_potential) {
    case 'possible':
      return 'Could start a family'
    case 'race':
      return 'Only Human pairs can have children'
    case 'age':
      return 'Both need to be adults'
    case 'gender':
      return 'This pair cannot have children'
    default:
      return null
  }
})

const { nextMilestone } = useRelationshipMilestone(() => props.relationship)

const bondCadence = computed(() => {
  const seconds = props.relationship.bond_tick_seconds
  if (!seconds) return null
  if (seconds === 60) return 'minute'
  if (seconds % 60 === 0) return `${seconds / 60} minutes`
  return `${seconds} seconds`
})

const bondChangeLabel = computed(() => {
  const change = props.relationship.bond_change_per_tick
  if (!change || !bondCadence.value) return null
  const sign = change > 0 ? '+' : '−'
  return `${sign}${Math.abs(change)} hearts every ${bondCadence.value}`
})

const affinityLabel = computed(() => (props.relationship.affinity < 0 ? 'HOSTILITY' : 'AFFINITY'))

const DISCOMFORT_LABEL = {
  feral: 'Feral ghoul unease',
  mutant: 'Super mutant unease',
  behemoth: 'Behemoth unease',
  synth_gen_1: 'Gen 1 synth unease',
  synth_gen_2: 'Gen 2 synth unease',
} as const

/** Why the bond is moving: race match, effective Charisma, and coworker unease. */
const bondFactors = computed(() => {
  const factors: string[] = []
  if (props.relationship.same_race === true) factors.push('Same race')
  else if (props.relationship.same_race === false) factors.push('Mixed races')
  if (typeof props.relationship.average_charisma === 'number') {
    factors.push(`Charisma ${props.relationship.average_charisma}`)
  }
  const source = props.relationship.discomfort_source
  if (source) factors.push(DISCOMFORT_LABEL[source])
  return factors
})
</script>

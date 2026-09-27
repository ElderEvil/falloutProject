<template>
  <Card
    class="relationship-card relationship-record--grid h-full min-h-96 gap-0 rounded-lg border-2 border-theme-primary/20 p-4 shadow-none ring-0"
  >
    <div class="flex flex-col gap-4">
      <div class="grid min-w-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-stretch gap-2">
        <button
          type="button"
          :title="`View ${dweller1Name}`"
          class="group flex min-h-36 min-w-0 flex-col items-center justify-center gap-1 rounded border border-theme-primary/20 bg-surface-sunken px-2 py-1.5 transition-colors hover:border-theme-primary/60 hover:bg-surface-hover focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
          @click="emit('select-dweller', relationship.dweller_1_id)"
        >
          <span
            class="dweller-portrait-frame flex size-16 shrink-0 items-center justify-center overflow-hidden rounded bg-black/30"
          >
            <DwellerPortrait
              :thumbnail-url="dweller1.thumbnail_url"
              :alt="dweller1Name"
              prefer-thumbnail
              image-class="h-full w-full object-cover"
              fallback-class="h-10 w-10 text-theme-primary/60"
            />
          </span>
          <span
            class="block w-full truncate text-center text-sm font-bold text-theme-primary group-hover:underline"
            >{{ dweller1Name }}</span
          >
          <span class="flex items-center justify-center gap-1.5">
            <span class="text-[0.65rem] font-bold text-theme-primary/70" title="Charisma"
              >C {{ dweller1.charisma }}</span
            >
            <DwellerGenderBadge :gender="dweller1.gender" size="sm" />
          </span>
          <DwellerRaceBadge
            :race="dweller1.visual_attributes?.race ?? 'human'"
            show-label
            size="sm"
          />
        </button>
        <div class="flex flex-col items-center justify-center gap-1 text-theme-primary/70">
          <Icon
            icon="mdi:heart"
            class="h-5 w-5 [filter:drop-shadow(0_0_4px_var(--color-theme-glow))]"
          />
          <Badge
            :variant="badgeVariant"
            class="relationship-badge mt-1 text-[0.625rem]"
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
        </div>
        <button
          type="button"
          :title="`View ${dweller2Name}`"
          class="group flex min-h-36 min-w-0 flex-col items-center justify-center gap-1 rounded border border-theme-primary/20 bg-surface-sunken px-2 py-1.5 transition-colors hover:border-theme-primary/60 hover:bg-surface-hover focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
          @click="emit('select-dweller', relationship.dweller_2_id)"
        >
          <span
            class="dweller-portrait-frame flex size-16 shrink-0 items-center justify-center overflow-hidden rounded bg-black/30"
          >
            <DwellerPortrait
              :thumbnail-url="dweller2.thumbnail_url"
              :alt="dweller2Name"
              prefer-thumbnail
              image-class="h-full w-full object-cover"
              fallback-class="h-10 w-10 text-theme-primary/60"
            />
          </span>
          <span
            class="block w-full truncate text-center text-sm font-bold text-theme-primary group-hover:underline"
            >{{ dweller2Name }}</span
          >
          <span class="flex items-center justify-center gap-1.5">
            <span class="text-[0.65rem] font-bold text-theme-primary/70" title="Charisma"
              >C {{ dweller2.charisma }}</span
            >
            <DwellerGenderBadge :gender="dweller2.gender" size="sm" />
          </span>
          <DwellerRaceBadge
            :race="dweller2.visual_attributes?.race ?? 'human'"
            show-label
            size="sm"
          />
        </button>
      </div>
      <div class="rounded border border-theme-primary/20 bg-surface-sunken p-3">
        <div class="flex items-center justify-between gap-2 text-xs">
          <span class="font-bold tracking-[0.08em] text-theme-primary/60">AFFINITY</span>
          <span class="font-bold text-theme-primary">{{ relationship.affinity }}/100</span>
        </div>
        <Progress :model-value="relationship.affinity" class="mt-2 h-2" />
        <div
          v-if="relationship.bond_growth_per_tick !== undefined"
          class="mt-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-xs"
        >
          <span v-if="relationship.affinity >= 100" class="text-theme-primary/70"
            >Bond at full strength</span
          >
          <template v-else-if="relationship.bond_growth_per_tick > 0">
            <span class="flex items-center gap-1 text-theme-primary/80">
              <Icon icon="mdi:heart-pulse" class="h-3.5 w-3.5" :ariaHidden="true" />
              Growing closer
            </span>
            <span v-if="bondCadence" class="font-bold text-theme-primary"
              >+{{ relationship.bond_growth_per_tick }} hearts every {{ bondCadence }}</span
            >
          </template>
          <span v-else class="text-theme-primary/60">Bond resting · meet in Living Quarters</span>
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
            ? 'animate-pulse motion-reduce:animate-none border-yellow-400/50 text-yellow-400'
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
        :icon="relationship.relationship_type === 'ex' ? 'mdi:heart-broken' : 'mdi:human-child'"
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
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import DwellerGenderBadge from '@/modules/dwellers/components/DwellerGenderBadge.vue'
import DwellerRaceBadge from '@/modules/dwellers/components/DwellerRaceBadge.vue'
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

/** Display name of the first relationship member. */
const dweller1Name = computed(() => formatDwellerName(props.dweller1))
/** Display name of the second relationship member. */
const dweller2Name = computed(() => formatDwellerName(props.dweller2))

/** Preview a few children in the family strip, with access to the rest. */
const CHILD_PREVIEW_LIMIT = 3
const visibleChildren = computed(() => props.children.slice(0, CHILD_PREVIEW_LIMIT))
const hiddenChildCount = computed(() => Math.max(0, props.children.length - CHILD_PREVIEW_LIMIT))

/** Format a dweller's full name for display. */
function formatDwellerName(dweller: DwellerShort): string {
  return `${dweller.first_name} ${dweller.last_name ?? ''}`.trim()
}

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

const familyPotentialLabel = computed(() => {
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
</script>

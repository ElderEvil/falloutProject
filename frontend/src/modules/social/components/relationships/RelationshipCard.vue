<template>
  <UCard v-if="props.viewMode === 'grid'" padding="md" class="relationship-card relationship-record--grid h-full">
    <div class="grid items-center gap-4 lg:grid-cols-[minmax(0,1fr)_12rem_auto]">
      <div class="grid min-w-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3">
        <button
          type="button"
          :title="`View ${dweller1Name}`"
          class="group flex min-w-0 flex-col items-center gap-1.5 rounded border border-theme-primary/20 bg-surface-sunken px-3 py-2 transition-colors hover:border-theme-primary/60 hover:bg-surface-hover focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
          @click="emit('select-dweller', relationship.dweller_1_id)"
        >
          <span class="block text-[0.65rem] font-bold tracking-[0.12em] text-theme-primary/55">DWELLER 01</span>
          <DwellerPortrait
            :thumbnail-url="dweller1.thumbnail_url"
            :alt="dweller1Name"
            prefer-thumbnail
            image-class="h-12 w-12 shrink-0 rounded object-cover"
          />
          <span class="block w-full truncate text-center text-sm font-bold text-theme-primary group-hover:underline">{{ dweller1Name }}</span>
          <span class="flex items-center justify-center gap-1.5">
            <span class="text-[0.65rem] font-bold tracking-[0.08em] text-theme-primary/55">LVL {{ dweller1.level }}</span>
            <DwellerGenderBadge :gender="dweller1.gender" size="sm" />
          </span>
        </button>
        <div class="flex flex-col items-center gap-1 text-theme-primary/70">
          <Icon icon="mdi:heart" class="h-5 w-5 [filter:drop-shadow(0_0_4px_var(--color-theme-glow))]" />
          <UBadge :variant="relationshipColor" class="relationship-badge mt-1 text-[0.625rem]">
            {{ relationship.relationship_type }}
          </UBadge>
        </div>
        <button
          type="button"
          :title="`View ${dweller2Name}`"
          class="group flex min-w-0 flex-col items-center gap-1.5 rounded border border-theme-primary/20 bg-surface-sunken px-3 py-2 transition-colors hover:border-theme-primary/60 hover:bg-surface-hover focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
          @click="emit('select-dweller', relationship.dweller_2_id)"
        >
          <span class="block text-[0.65rem] font-bold tracking-[0.12em] text-theme-primary/55">DWELLER 02</span>
          <DwellerPortrait
            :thumbnail-url="dweller2.thumbnail_url"
            :alt="dweller2Name"
            prefer-thumbnail
            image-class="h-12 w-12 shrink-0 rounded object-cover"
          />
          <span class="block w-full truncate text-center text-sm font-bold text-theme-primary group-hover:underline">{{ dweller2Name }}</span>
          <span class="flex items-center justify-center gap-1.5">
            <span class="text-[0.65rem] font-bold tracking-[0.08em] text-theme-primary/55">LVL {{ dweller2.level }}</span>
            <DwellerGenderBadge :gender="dweller2.gender" size="sm" />
          </span>
        </button>
      </div>

      <div class="rounded border border-theme-primary/20 bg-surface-sunken p-3">
        <div class="flex items-center justify-between gap-2 text-xs">
          <span class="font-bold tracking-[0.08em] text-theme-primary/60">AFFINITY</span>
          <span class="font-bold text-theme-primary">{{ relationship.affinity }}/100</span>
        </div>
        <UProgressBar :model-value="relationship.affinity" :height="8" class="mt-2" />
        <p v-if="nextMilestone" class="mt-2 text-xs leading-4 text-theme-primary/60">
          {{ nextMilestone }}
        </p>
      </div>

      <div class="flex flex-wrap justify-end gap-2">
        <UButton
          v-if="relationship.relationship_type === 'acquaintance' && relationship.affinity >= 70"
          @click="$emit('initiate-romance')"
          size="sm"
        >
          Romance
        </UButton>
        <UButton
          v-if="relationship.relationship_type === 'romantic'"
          @click="$emit('make-partners')"
          size="sm"
        >
          Partner
        </UButton>
        <UButton
          v-if="relationship.relationship_type === 'partner' && relationship.affinity >= 85"
          @click="$emit('marry')"
          size="sm"
        >
          Marry
        </UButton>
        <UButton
          v-if="isRelationshipType(relationship.relationship_type, COMMITTED_RELATIONSHIP_TYPES)"
          @click="$emit('break-up')"
          variant="danger"
          size="sm"
        >
          Break Up
        </UButton>
      </div>
    </div>
    <div
      v-if="isPartnerLinked"
      class="mt-3 flex flex-wrap items-center gap-1.5 border-t border-theme-primary/15 pt-2"
    >
      <span class="text-[0.65rem] font-bold uppercase tracking-[0.1em] text-theme-primary/55">GEN {{ generation }}</span>
      <span class="flex items-center gap-1 text-[0.65rem] font-bold uppercase tracking-[0.1em] text-theme-primary/55">
        <Icon icon="mdi:human-child" class="h-3.5 w-3.5" />
        Children<template v-if="children.length"> ({{ children.length }})</template>
      </span>
      <span
        v-if="pregnancy"
        class="flex items-center gap-1 rounded border px-1.5 py-0.5 text-[0.65rem] font-bold uppercase tracking-[0.1em]"
        :class="pregnancy.is_due ? 'animate-pulse border-yellow-400/50 text-yellow-400' : 'border-theme-primary/30 text-theme-primary/70'"
      >
        <Icon icon="mdi:baby-carriage" class="h-3.5 w-3.5" />
        {{ pregnancy.is_due ? 'Due!' : 'Expecting' }}
      </span>
      <template v-if="children.length">
        <ChildChip
          v-for="child in children"
          :key="child.id"
          :dweller="child"
          @select="emit('select-dweller', $event)"
        />
      </template>
      <span v-else class="text-xs text-theme-primary/40">No children yet</span>
    </div>
  </UCard>
  <UCard v-else padding="sm" class="relationship-record--list">
    <div class="grid items-center gap-3 md:grid-cols-[minmax(0,1fr)_10rem_auto]">
      <div class="min-w-0">
        <div class="flex min-w-0 items-center gap-2">
          <DwellerPortrait
            :thumbnail-url="dweller1.thumbnail_url"
            :alt="dweller1Name"
            prefer-thumbnail
            image-class="h-8 w-8 shrink-0 rounded object-cover"
          />
          <button
            type="button"
            :title="`View ${dweller1Name}`"
            class="min-w-0 truncate text-left font-bold text-theme-primary hover:underline focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
            @click="emit('select-dweller', relationship.dweller_1_id)"
          >
            {{ dweller1Name }}
          </button>
          <Icon icon="mdi:heart" class="h-4 w-4 shrink-0 text-theme-primary/70" />
          <DwellerPortrait
            :thumbnail-url="dweller2.thumbnail_url"
            :alt="dweller2Name"
            prefer-thumbnail
            image-class="h-8 w-8 shrink-0 rounded object-cover"
          />
          <button
            type="button"
            :title="`View ${dweller2Name}`"
            class="min-w-0 truncate text-left font-bold text-theme-primary hover:underline focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
            @click="emit('select-dweller', relationship.dweller_2_id)"
          >
            {{ dweller2Name }}
          </button>
        </div>
        <UBadge :variant="relationshipColor" class="relationship-badge mt-1 text-[0.625rem]">
          {{ relationship.relationship_type }}
        </UBadge>
      </div>
      <div class="rounded border border-theme-primary/15 bg-surface-sunken px-2.5 py-2">
        <div class="flex items-center justify-between text-xs text-theme-primary/70">
          <span>AFFINITY</span>
          <span class="font-bold text-theme-primary">{{ relationship.affinity }}/100</span>
        </div>
        <UProgressBar :model-value="relationship.affinity" :height="6" class="mt-1.5" />
      </div>
      <div class="flex flex-wrap justify-end gap-2">
        <UButton
          v-if="relationship.relationship_type === 'acquaintance' && relationship.affinity >= 70"
          @click="emit('initiate-romance')"
          size="sm"
        >
          Romance
        </UButton>
        <UButton v-if="relationship.relationship_type === 'romantic'" @click="emit('make-partners')" size="sm">
          Partner
        </UButton>
        <UButton
          v-if="relationship.relationship_type === 'partner' && relationship.affinity >= 85"
          @click="emit('marry')"
          size="sm"
        >
          Marry
        </UButton>
        <UButton
          v-if="isRelationshipType(relationship.relationship_type, COMMITTED_RELATIONSHIP_TYPES)"
          @click="emit('break-up')"
          variant="danger"
          size="sm"
        >
          Break Up
        </UButton>
      </div>
    </div>
    <div
      v-if="isPartnerLinked"
      class="mt-3 flex flex-wrap items-center gap-1.5 border-t border-theme-primary/15 pt-2"
    >
      <span class="text-[0.65rem] font-bold uppercase tracking-[0.1em] text-theme-primary/55">GEN {{ generation }}</span>
      <span class="flex items-center gap-1 text-[0.65rem] font-bold uppercase tracking-[0.1em] text-theme-primary/55">
        <Icon icon="mdi:human-child" class="h-3.5 w-3.5" />
        Children<template v-if="children.length"> ({{ children.length }})</template>
      </span>
      <span
        v-if="pregnancy"
        class="flex items-center gap-1 rounded border px-1.5 py-0.5 text-[0.65rem] font-bold uppercase tracking-[0.1em]"
        :class="pregnancy.is_due ? 'animate-pulse border-yellow-400/50 text-yellow-400' : 'border-theme-primary/30 text-theme-primary/70'"
      >
        <Icon icon="mdi:baby-carriage" class="h-3.5 w-3.5" />
        {{ pregnancy.is_due ? 'Due!' : 'Expecting' }}
      </span>
      <template v-if="children.length">
        <ChildChip
          v-for="child in children"
          :key="child.id"
          :dweller="child"
          @select="emit('select-dweller', $event)"
        />
      </template>
      <span v-else class="text-xs text-theme-primary/40">No children yet</span>
    </div>
  </UCard>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import {
  COMMITTED_RELATIONSHIP_TYPES,
  isRelationshipType,
  PARTNER_LINKED_RELATIONSHIP_TYPES,
  RELATIONSHIP_TYPE_VARIANT,
  type Relationship,
} from '../../models/relationship'
import { useRelationshipMilestone } from '../../composables/useRelationshipMilestone'
import type { Pregnancy } from '../../models/pregnancy'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import DwellerGenderBadge from '@/modules/dwellers/components/DwellerGenderBadge.vue'
import ChildChip from './ChildChip.vue'
import UCard from '@/core/components/ui/UCard.vue'
import UBadge from '@/core/components/ui/UBadge.vue'
import UButton from '@/core/components/ui/UButton.vue'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'

interface Props {
  relationship: Relationship
  dweller1: DwellerShort
  dweller2: DwellerShort
  children?: DwellerShort[]
  viewMode?: 'list' | 'grid'
  pregnancy?: Pregnancy | null
  generation?: number
}

const props = withDefaults(defineProps<Props>(), {
  viewMode: 'list',
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

const dweller1Name = computed(() => formatDwellerName(props.dweller1))
const dweller2Name = computed(() => formatDwellerName(props.dweller2))

function formatDwellerName(dweller: DwellerShort): string {
  return `${dweller.first_name} ${dweller.last_name ?? ''}`.trim()
}

const relationshipColor = computed(
  () => RELATIONSHIP_TYPE_VARIANT[props.relationship.relationship_type] ?? 'success'
)

const isPartnerLinked = computed(() =>
  isRelationshipType(props.relationship.relationship_type, PARTNER_LINKED_RELATIONSHIP_TYPES)
)

const { nextMilestone } = useRelationshipMilestone(() => props.relationship)
</script>

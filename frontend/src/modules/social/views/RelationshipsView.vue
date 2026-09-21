<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useRelationshipStore } from '../stores/relationship'
import { usePregnancyStore } from '../stores/pregnancy'
import { isRelationshipType, PARTNER_LINKED_RELATIONSHIP_TYPES } from '../models/relationship'
import { allChildren } from '../models/dwellerFamily'
import PageHeader from '@/core/components/common/PageHeader.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import VaultPageShell from '@/core/components/common/VaultPageShell.vue'
import RelationshipList from '../components/relationships/RelationshipList.vue'
import PregnancyTracker from '../components/pregnancy/PregnancyTracker.vue'
import ChildrenList from '../components/relationships/ChildrenList.vue'
import UTabs from '@/core/components/ui/UTabs.vue'

const route = useRoute()
const router = useRouter()
const relationshipStore = useRelationshipStore()
const pregnancyStore = usePregnancyStore()
const { filter: dwellerStore } = useDwellerStore()
const authStore = useAuthStore()

const vaultId = computed(() => route.params.id as string)
const activeStage = ref<'forming' | 'partners' | 'pregnancies' | 'children'>('forming')

// Stats
/** Total number of relationships in the vault. */
const totalRelationships = computed(() => relationshipStore.relationships.length)
/** Number of relationships that are committed partner links. */
const partnersCount = computed(
  () =>
    relationshipStore.relationships.filter((r) =>
      isRelationshipType(r.relationship_type, PARTNER_LINKED_RELATIONSHIP_TYPES)
    ).length
)
/** Number of active pregnancies in the vault. */
const pregnanciesCount = computed(() => pregnancyStore.pregnancies.length)
/** Number of children currently in the vault. */
const childrenCount = computed(() => allChildren(dwellerStore.allDwellers).length)

// Stages configuration
/** Stage definitions with per-stage relationship counts. */
const stages = computed(() => [
  {
    id: 'forming',
    label: 'Forming',
    icon: 'mdi:account-group',
    count: relationshipStore.relationships.filter(
      (r) => !isRelationshipType(r.relationship_type, PARTNER_LINKED_RELATIONSHIP_TYPES)
    ).length,
  },
  {
    id: 'partners',
    label: 'Partners',
    icon: 'mdi:human-male-female',
    count: partnersCount.value,
  },
  {
    id: 'pregnancies',
    label: 'Pregnancies',
    icon: 'mdi:baby-carriage',
    count: pregnanciesCount.value,
  },
  {
    id: 'children',
    label: 'Children',
    icon: 'mdi:human-child',
    count: childrenCount.value,
  },
])

/** Tab descriptors for the family stage switcher. */
const familyTabs = computed(() => stages.value.map((stage) => ({ key: stage.id, label: `${stage.label} (${stage.count})` })))

/** Switch the active family stage tab. */
function setActiveStage(stage: string) {
  activeStage.value = stage as typeof activeStage.value
}

onMounted(async () => {
  if (vaultId.value && authStore.token) {
    await Promise.all([
      relationshipStore.fetchVaultRelationships(vaultId.value),
      pregnancyStore.fetchVaultPregnancies(vaultId.value),
      dwellerStore.fetchAllDwellers(vaultId.value, authStore.token),
    ])
  }
})

/** Navigate to the dweller detail page for the given dweller. */
const navigateToDweller = (dwellerId: string) => {
  router.push(`/vault/${vaultId.value}/dwellers/${dwellerId}`)
}
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <!-- Main View -->
    <VaultPageShell>
      <PageContentRail class="flex flex-col gap-6">
        <PageHeader
          title="Relationships &amp; Family"
          icon="mdi:heart-multiple"
          subtitle="Track relationships, pregnancies, and the next generation of your vault."
        >
          <template #actions>
            <span class="flex items-center gap-2 rounded border border-theme-primary/20 bg-surface-sunken px-3 py-2">
              <Icon icon="mdi:heart-multiple" class="h-4 w-4 text-theme-primary/70" />
              <span class="total-relationships-count text-2xl font-bold leading-none text-theme-primary">{{ totalRelationships }}</span>
              <span class="text-[0.65rem] font-bold uppercase tracking-[0.1em] text-theme-primary/55">
                {{ totalRelationships === 1 ? 'relationship' : 'relationships' }}
              </span>
            </span>
          </template>
        </PageHeader>

          <UTabs
            :model-value="activeStage"
            :tabs="familyTabs"
            @update:model-value="setActiveStage"
          >
            <template #default>
              <section class="min-w-0">
              <!-- Stage 1: All Dwellers / Forming Relationships -->
              <div v-if="activeStage === 'forming'" class="space-y-5">
                <div>
                  <h2 class="flex items-center gap-2 text-lg font-bold text-theme-primary">
                    <Icon icon="mdi:account-group" class="h-5 w-5" />
                    Forming Relationships
                  </h2>
                  <p class="mt-1 text-sm leading-6 text-theme-primary/60">
                    Dwellers in the same room will gradually increase their affinity. Romance can
                    begin at 70+ affinity.
                  </p>
                </div>
                <RelationshipList
                  v-if="vaultId"
                  :vaultId="vaultId"
                  stageFilter="forming"
                  @select-dweller="navigateToDweller"
                />
              </div>

              <!-- Stage 2: Partners -->
              <div v-if="activeStage === 'partners'" class="space-y-5">
                <div>
                  <h2 class="flex items-center gap-2 text-lg font-bold text-theme-primary">
                    <Icon icon="mdi:human-male-female" class="h-5 w-5" />
                    Partner Couples
                  </h2>
                  <p class="mt-1 text-sm leading-6 text-theme-primary/60">
                    Committed partners in living quarters have a chance to conceive (configurable
                    via game settings).
                  </p>
                </div>
                <RelationshipList
                  v-if="vaultId"
                  :vaultId="vaultId"
                  stageFilter="partners"
                  @select-dweller="navigateToDweller"
                />
              </div>

              <!-- Stage 3: Pregnancies -->
              <div v-if="activeStage === 'pregnancies'" class="space-y-5">
                <div>
                  <h2 class="flex items-center gap-2 text-lg font-bold text-theme-primary">
                    <Icon icon="mdi:baby-carriage" class="h-5 w-5" />
                    Active Pregnancies
                  </h2>
                  <p class="mt-1 text-sm leading-6 text-theme-primary/60">
                    Pregnancies last 3 hours. Babies inherit traits from both parents.
                  </p>
                </div>
                <PregnancyTracker v-if="vaultId" :vaultId="vaultId" :autoRefresh="true" />
              </div>

              <!-- Stage 4: Children -->
              <div v-if="activeStage === 'children'" class="space-y-5">
                <div>
                  <h2 class="flex items-center gap-2 text-lg font-bold text-theme-primary">
                    <Icon icon="mdi:human-child" class="h-5 w-5" />
                    Growing Children
                  </h2>
                  <p class="mt-1 text-sm leading-6 text-theme-primary/60">
                    Children grow to adults after 3 hours. They consume resources but cannot work
                    until grown.
                  </p>
                </div>
                <ChildrenList v-if="vaultId" :vaultId="vaultId" @select="navigateToDweller" />
              </div>
              </section>
            </template>
          </UTabs>
      </PageContentRail>
    </VaultPageShell>
  </div>
</template>

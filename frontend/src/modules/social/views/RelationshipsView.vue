<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { useRelationshipStore } from '../stores/relationship'
import { isRelationshipType, PARTNER_LINKED_RELATIONSHIP_TYPES } from '../models/relationship'
import PageHeader from '@/core/components/common/PageHeader.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import SidePanel from '@/core/components/common/SidePanel.vue'
import RelationshipList from '../components/relationships/RelationshipList.vue'
import PregnancyTracker from '../components/pregnancy/PregnancyTracker.vue'
import ChildrenList from '../components/relationships/ChildrenList.vue'
import UTabs from '@/core/components/ui/UTabs.vue'

const route = useRoute()
const router = useRouter()
const { isCollapsed } = useSidePanel()
const relationshipStore = useRelationshipStore()
const { filter: dwellerStore } = useDwellerStore()
const authStore = useAuthStore()

const vaultId = computed(() => route.params.id as string)
const activeStage = ref<'forming' | 'partners' | 'pregnancies' | 'children'>('forming')

// Stats
const totalRelationships = computed(() => relationshipStore.relationships.length)
const partnersCount = computed(
  () =>
    relationshipStore.relationships.filter((r) =>
      isRelationshipType(r.relationship_type, PARTNER_LINKED_RELATIONSHIP_TYPES)
    ).length
)
const pregnanciesCount = computed(() => relationshipStore.pregnancies.length)
const childrenCount = computed(
  () => dwellerStore.dwellers.filter((d) => d.age_group === 'child').length
)

const summaryMetrics = computed(() => [
  { icon: 'mdi:heart-multiple', label: 'Total Relationships', value: totalRelationships.value },
  { icon: 'mdi:human-male-female', label: 'Partner Couples', value: partnersCount.value },
  { icon: 'mdi:baby-carriage', label: 'Active Pregnancies', value: pregnanciesCount.value },
  { icon: 'mdi:human-child', label: 'Growing Children', value: childrenCount.value },
])

// Stages configuration
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

const familyTabs = computed(() => stages.value.map((stage) => ({ key: stage.id, label: `${stage.label} (${stage.count})` })))

function setActiveStage(stage: string) {
  activeStage.value = stage as typeof activeStage.value
}

onMounted(async () => {
  if (vaultId.value && authStore.token) {
    await Promise.all([
      relationshipStore.fetchVaultRelationships(vaultId.value),
      relationshipStore.fetchVaultPregnancies(vaultId.value),
      dwellerStore.fetchAllDwellers(vaultId.value, authStore.token),
    ])
  }
})

const navigateToDweller = (dwellerId: string) => {
  router.push(`/vault/${vaultId.value}/dwellers/${dwellerId}`)
}
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <!-- Main View -->
    <div class="vault-layout">
      <!-- Side Panel -->
      <SidePanel />

      <!-- Main Content Area -->
      <main class="main-content" :class="{ collapsed: isCollapsed }">
        <PageContentRail class="flex flex-col gap-6">
          <PageHeader
            title="Relationships &amp; Family"
            icon="mdi:heart-multiple"
            subtitle="Track relationships, pregnancies, and the next generation of your vault."
          />

          <section class="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div
              v-for="metric in summaryMetrics"
              :key="metric.label"
              class="flex items-center gap-3 rounded border border-theme-primary/20 bg-transparent p-4 transition-colors hover:border-theme-primary/50 hover:bg-theme-glow/10"
            >
              <Icon
                :icon="metric.icon"
                class="h-7 w-7 shrink-0 text-theme-primary/70 [filter:drop-shadow(0_0_4px_var(--color-theme-glow))]"
              />
              <div class="min-w-0">
                <div class="stat-value text-2xl font-bold leading-none text-theme-primary">{{ metric.value }}</div>
                <div class="mt-1 truncate text-[0.65rem] font-bold tracking-[0.1em] text-theme-primary/60">
                  {{ metric.label }}
                </div>
              </div>
            </div>
          </section>

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
                <ChildrenList v-if="vaultId" :vaultId="vaultId" />
              </div>
              </section>
            </template>
          </UTabs>
        </PageContentRail>
      </main>
    </div>
  </div>
</template>

<style scoped>
.vault-layout {
  display: flex;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  margin-left: 240px;
  transition: margin-left 0.3s ease;
}

.main-content.collapsed {
  margin-left: 64px;
}

</style>

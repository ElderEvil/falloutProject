<script setup lang="ts">
import { ref, watch } from 'vue'
import { Tabs, TabsList, TabsTrigger } from '@/core/components/ui/tabs'
import { useDwellerDetailContext } from './DwellerDetailContext'
import { dwellerDetailSections } from '../composables/useDwellerDetailSections'

const ctx = useDwellerDetailContext()

const normalizeTab = (tab: string) =>
  dwellerDetailSections.some((section) => section.key === tab) ? tab : 'profile'

const activeTab = ref(normalizeTab(ctx.initialTab.value ?? 'profile'))
watch(
  () => ctx.initialTab.value,
  (tab) => {
    if (tab) activeTab.value = normalizeTab(tab)
  }
)

const tabs = dwellerDetailSections.map(({ key, label }) => ({ key, label }))
const sectionComponent = (key: string) =>
  dwellerDetailSections.find((section) => section.key === key)?.component
</script>

<template>
  <div class="dweller-panel">
    <Tabs :model-value="activeTab" @update:model-value="activeTab = String($event)">
      <TabsList>
        <TabsTrigger v-for="tab in tabs" :key="tab.key" :value="tab.key">
          {{ tab.label }}
        </TabsTrigger>
      </TabsList>
      <div class="tab-content">
        <component :is="sectionComponent(activeTab)" />
      </div>
    </Tabs>
  </div>
</template>

<style scoped>
.dweller-panel {
  width: 100%;
  padding: 1.5rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid var(--color-theme-glow);
  border-radius: 8px;
  box-shadow: 0 0 15px var(--color-theme-glow);
}

.tab-content {
  min-height: 0;
}
</style>

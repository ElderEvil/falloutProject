<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { WastelandLocationWithDwellers, VaultMarkerRead } from '../models/map'

interface Props {
  locations: WastelandLocationWithDwellers[]
  vaultMarkers: VaultMarkerRead[]
  selectedMarkerId?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  selectedMarkerId: null,
})

const emit = defineEmits<{
  (
    e: 'marker-select',
    payload:
      | { kind: 'location'; data: WastelandLocationWithDwellers }
      | { kind: 'vault'; data: VaultMarkerRead }
  ): void
}>()

// Panel open/close state
const isOpen = defineModel<boolean>('open', { default: false })

interface MarkerGroup {
  type: string
  label: string
  icon: string
  items: Array<{
    id: string
    name: string
    kind: 'location' | 'vault'
    data: WastelandLocationWithDwellers | VaultMarkerRead
  }>
}

const typeOrder: Array<{ type: string; label: string; icon: string }> = [
  { type: 'home_vault', label: 'Home Vault', icon: 'mdi:home-city' },
  { type: 'origin', label: 'Origin', icon: 'mdi:flag' },
  { type: 'visited', label: 'Visited', icon: 'mdi:eye' },
  { type: 'discovery', label: 'Discovery', icon: 'mdi:compass' },
  { type: 'vault', label: 'Vault Signal', icon: 'mdi:radioactive' },
]

const groups = computed<MarkerGroup[]>(() => {
  const byType = new Map<string, MarkerGroup['items']>()

  for (const loc of props.locations) {
    if (!byType.has(loc.type)) byType.set(loc.type, [])
    byType.get(loc.type)!.push({ id: `loc-${loc.id}`, name: loc.name, kind: 'location', data: loc })
  }

  for (let i = 0; i < props.vaultMarkers.length; i++) {
    const vm = props.vaultMarkers[i]
    if (!byType.has(vm.type)) byType.set(vm.type, [])
    byType.get(vm.type)!.push({ id: `vault-${i}`, name: vm.name, kind: 'vault', data: vm })
  }

  return typeOrder
    .filter((t) => byType.has(t.type) && byType.get(t.type)!.length > 0)
    .map((t) => ({
      type: t.type,
      label: t.label,
      icon: t.icon,
      items: byType.get(t.type)!,
    }))
})

const totalCount = computed(() => props.locations.length + props.vaultMarkers.length)

function handleItemClick(item: MarkerGroup['items'][number]) {
  emit('marker-select', { kind: item.kind, data: item.data } as any)
}
</script>

<template>
  <div class="marker-list-wrapper" :class="{ open: isOpen }">
    <!-- Toggle button -->
    <button
      class="marker-list-toggle"
      :aria-label="isOpen ? 'Close marker list' : 'Open marker list'"
      :title="isOpen ? 'Close marker list' : 'Open marker list'"
      @click="isOpen = !isOpen"
    >
      <Icon :icon="isOpen ? 'mdi:chevron-right' : 'mdi:format-list-bulleted'" class="toggle-icon" />
    </button>

    <!-- Panel -->
    <aside v-show="isOpen" class="marker-list-panel" role="complementary" aria-label="Marker list">
      <div class="panel-header">
        <span class="panel-title">MARKERS</span>
        <span class="panel-count">{{ totalCount }}</span>
      </div>

      <div class="panel-body">
        <div v-for="group in groups" :key="group.type" class="marker-group">
          <div class="group-header">
            <Icon :icon="group.icon" class="group-icon" />
            <span class="group-label">{{ group.label }}</span>
            <span class="group-count">{{ group.items.length }}</span>
          </div>

          <button
            v-for="item in group.items"
            :key="item.id"
            class="marker-row"
            :class="{ selected: selectedMarkerId === item.id }"
            @click="handleItemClick(item)"
          >
            <span class="marker-name">{{ item.name }}</span>
          </button>
        </div>

        <div v-if="groups.length === 0" class="empty-state">No markers yet</div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.marker-list-wrapper {
  position: absolute;
  top: 8px;
  right: 8px;
  bottom: 8px;
  z-index: 10;
  display: flex;
  flex-direction: row-reverse;
  align-items: flex-start;
  gap: 4px;
}

.marker-list-toggle {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--color-surface) 90%, transparent);
  border: 1px solid var(--color-theme-primary);
  border-radius: 2px;
  color: var(--color-theme-primary);
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.marker-list-toggle:hover {
  background: var(--color-theme-glow);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.toggle-icon {
  width: 16px;
  height: 16px;
}

.marker-list-panel {
  width: 200px;
  max-height: calc(100% - 16px);
  background: color-mix(in srgb, var(--color-surface) 92%, transparent);
  border: 1px solid var(--color-theme-primary);
  border-radius: 2px;
  box-shadow: 0 0 10px var(--color-theme-glow);
  font-family: var(--font-family-mono);
  font-size: 10px;
  color: var(--color-theme-primary);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  border-bottom: 1px solid var(--color-theme-primary);
  opacity: 0.7;
  flex-shrink: 0;
}

.panel-title {
  font-size: 9px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.panel-count {
  font-size: 9px;
  opacity: 0.6;
}

.panel-body {
  overflow-y: auto;
  flex: 1;
  padding: 4px 0;
}

.marker-group {
  margin-bottom: 2px;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  opacity: 0.5;
  font-size: 8px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.group-icon {
  width: 10px;
  height: 10px;
  flex-shrink: 0;
}

.group-label {
  flex: 1;
}

.group-count {
  opacity: 0.5;
}

.marker-row {
  display: block;
  width: 100%;
  padding: 3px 8px 3px 22px;
  text-align: left;
  background: transparent;
  border: none;
  color: var(--color-theme-primary);
  cursor: pointer;
  font-family: var(--font-family-mono);
  font-size: 10px;
  transition: background var(--transition-fast);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.marker-row:hover {
  background: var(--color-theme-glow);
}

.marker-row.selected {
  background: var(--color-theme-glow);
  box-shadow: inset 2px 0 0 var(--color-theme-primary);
}

.marker-name {
  pointer-events: none;
}

.empty-state {
  padding: 12px 8px;
  text-align: center;
  opacity: 0.4;
  font-size: 9px;
}

/* Vault type styling */
.marker-group:last-child .group-icon {
  color: var(--color-warning);
}

/* Scrollbar styling */
.panel-body::-webkit-scrollbar {
  width: 4px;
}

.panel-body::-webkit-scrollbar-track {
  background: transparent;
}

.panel-body::-webkit-scrollbar-thumb {
  background: var(--color-theme-primary);
  opacity: 0.3;
  border-radius: 2px;
}
</style>

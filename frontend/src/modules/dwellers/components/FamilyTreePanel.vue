<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useLineage } from '../composables/useLineage'
import type { LineageMember } from '../services/lineageService'
import { useDwellerDetailContext } from './DwellerDetailContext'

const ctx = useDwellerDetailContext()

const dwellerId = computed(() => ctx.dweller.value?.id ?? ctx.dwellerId.value)
const dwellerName = computed(() => {
  const d = ctx.dweller.value
  return d ? [d.first_name, d.last_name].filter(Boolean).join(' ') : ''
})

const { lineage, isLoading, error, load, select } = useLineage(
  () => dwellerId.value,
  (id) => ctx.actions.navigateToDweller(id)
)

const partnerStage = (member: LineageMember) => member.relationship_type ?? 'partner'
const isDead = (member: LineageMember) => member.is_dead
</script>

<template>
  <div class="family-tree-panel">
    <div class="family-tree-header">
      <h3 class="family-tree-title">Family Tree</h3>
      <div class="family-tree-actions">
        <span v-if="lineage" class="tree-generation">Gen {{ lineage.generation }}</span>
        <button
          type="button"
          class="tree-refresh"
          :disabled="isLoading"
          title="Refresh family tree"
          @click="load"
        >
          ⟳
        </button>
      </div>
    </div>

    <div v-if="isLoading" class="family-tree-loading">Loading lineage…</div>

    <div v-else-if="error" class="family-tree-error">
      <p>{{ error }}</p>
      <button type="button" class="tree-retry" @click="load">Retry</button>
    </div>

    <div v-else-if="lineage" class="family-tree-rows">
      <div class="tree-row">
        <span class="tree-label">Parents</span>
        <div class="tree-nodes">
          <button
            v-for="member in lineage.parents"
            :key="member.id"
            type="button"
            class="tree-node"
            :class="{ 'tree-node-dead': isDead(member) }"
            :title="member.first_name + ' ' + (member.last_name || '')"
            @click="select(member)"
          >
            <Icon v-if="isDead(member)" icon="mdi:skull" class="node-icon" />
            {{ member.first_name }} {{ member.last_name }}
          </button>
          <span v-if="!lineage.parents.length" class="tree-empty">—</span>
        </div>
      </div>

      <div class="tree-row">
        <span class="tree-label">Dweller</span>
        <div class="tree-nodes">
          <span class="tree-node tree-node-self">{{ dwellerName || 'This Dweller' }}</span>
          <button
            v-for="member in lineage.partners"
            :key="member.id"
            type="button"
            class="tree-node tree-node-partner"
            :class="{ 'tree-node-dead': isDead(member) }"
            :title="member.first_name + ' ' + (member.last_name || '')"
            @click="select(member)"
          >
            <Icon
              :icon="member.relationship_type === 'MARRIED' ? 'mdi:ring' : 'mdi:heart'"
              class="node-icon"
            />
            {{ member.first_name }} {{ member.last_name }}
            <span class="node-badge">{{ partnerStage(member) }}</span>
            <span v-if="member.affinity != null" class="node-affinity">{{ member.affinity }}♥</span>
          </button>
          <span v-if="!lineage.partners.length" class="tree-empty">—</span>
        </div>
      </div>

      <div class="tree-row">
        <span class="tree-label">Siblings</span>
        <div class="tree-nodes">
          <button
            v-for="member in lineage.siblings"
            :key="member.id"
            type="button"
            class="tree-node"
            :class="{ 'tree-node-dead': isDead(member) }"
            :title="member.first_name + ' ' + (member.last_name || '')"
            @click="select(member)"
          >
            <Icon v-if="isDead(member)" icon="mdi:skull" class="node-icon" />
            {{ member.first_name }} {{ member.last_name }}
          </button>
          <span v-if="!lineage.siblings.length" class="tree-empty">—</span>
        </div>
      </div>

      <div class="tree-row">
        <span class="tree-label">Children</span>
        <div class="tree-nodes">
          <button
            v-for="member in lineage.children"
            :key="member.id"
            type="button"
            class="tree-node"
            :class="{ 'tree-node-dead': isDead(member) }"
            :title="member.first_name + ' ' + (member.last_name || '')"
            @click="select(member)"
          >
            <Icon v-if="isDead(member)" icon="mdi:skull" class="node-icon" />
            {{ member.first_name }} {{ member.last_name }}
          </button>
          <span v-if="!lineage.children.length" class="tree-empty">—</span>
        </div>
      </div>
    </div>

    <div v-else class="family-tree-empty">No lineage data.</div>
  </div>
</template>

<style scoped>
.family-tree-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.family-tree-title {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.family-tree-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.tree-generation {
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
}

.tree-refresh {
  background: transparent;
  border: 1px solid var(--color-theme-primary);
  border-radius: 0.375rem;
  color: var(--color-theme-primary);
  width: 1.75rem;
  height: 1.75rem;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
}

.tree-refresh:hover:not(:disabled) {
  background: rgba(0, 255, 0, 0.18);
}

.tree-refresh:disabled {
  opacity: 0.4;
  cursor: default;
}

.family-tree-rows {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.tree-row {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  flex-wrap: wrap;
}

.tree-label {
  flex: 0 0 5rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
  padding-top: 0.4rem;
  font-size: 0.875rem;
}

.tree-nodes {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}

.tree-node {
  background: rgba(0, 255, 0, 0.08);
  border: 1px solid var(--color-theme-primary);
  border-radius: 0.375rem;
  padding: 0.4rem 0.75rem;
  color: var(--color-theme-primary);
  cursor: pointer;
  transition: all 0.2s;
  font-family: 'Courier New', monospace;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.tree-node:hover {
  box-shadow: 0 0 12px var(--color-theme-glow);
  background: rgba(0, 255, 0, 0.18);
}

.tree-node-self {
  cursor: default;
  opacity: 0.85;
  background: rgba(0, 255, 0, 0.2);
}

.tree-node-partner {
  border-color: #ff4d4d;
  color: #ff6b6b;
}

.tree-node-dead {
  opacity: 0.5;
  text-decoration: line-through;
}

.node-icon {
  font-size: 0.875rem;
  opacity: 0.8;
}

.node-badge {
  font-size: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: rgba(255, 77, 77, 0.15);
  border: 1px solid #ff4d4d;
  border-radius: 999px;
  padding: 0.05rem 0.4rem;
  color: #ff6b6b;
}

.node-affinity {
  font-size: 0.625rem;
  opacity: 0.8;
}

.tree-empty {
  opacity: 0.4;
  color: var(--color-theme-primary);
}

.family-tree-loading,
.family-tree-empty {
  text-align: center;
  padding: 1.5rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
}

.family-tree-error {
  text-align: center;
  padding: 1.5rem;
  color: #ff6b6b;
}

.tree-retry {
  margin-top: 0.75rem;
  background: transparent;
  border: 1px solid var(--color-theme-primary);
  border-radius: 0.375rem;
  color: var(--color-theme-primary);
  padding: 0.375rem 1rem;
  cursor: pointer;
}

.tree-retry:hover {
  background: rgba(0, 255, 0, 0.18);
}
</style>

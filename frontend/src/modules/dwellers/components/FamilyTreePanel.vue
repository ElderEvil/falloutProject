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
    <div class="family-tree-header panel-header">
      <h3 class="family-tree-title panel-title">Family Tree</h3>
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

    <div v-else-if="lineage" class="family-tree">
      <section class="tier" aria-label="Parents">
        <span class="tier-caption">Parents</span>
        <div class="tier-nodes bus">
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
      </section>

      <div class="trunk" aria-hidden="true" />

      <section class="tier" aria-label="Household">
        <span class="tier-caption">Dweller</span>
        <div class="tier-nodes tier-nodes-column">
          <div class="pair bus">
            <span class="tree-node tree-node-self">{{ dwellerName || 'This Dweller' }}</span>
            <template v-for="member in lineage.partners" :key="member.id">
              <span class="pair-bond">
                {{ partnerStage(member) }}
                <span v-if="member.affinity != null" class="bond-affinity">
                  <span class="affinity-bar" aria-hidden="true">
                    <span class="affinity-fill" :style="{ width: member.affinity + '%' }" />
                  </span>
                  {{ member.affinity }}♥
                </span>
              </span>
              <button
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
              </button>
            </template>
            <span v-if="!lineage.partners.length" class="tree-empty">—</span>
          </div>
          <div v-if="lineage.siblings.length" class="siblings">
            <span class="siblings-caption">Siblings</span>
            <button
              v-for="member in lineage.siblings"
              :key="member.id"
              type="button"
              class="tree-node tree-node-sibling"
              :class="{ 'tree-node-dead': isDead(member) }"
              :title="member.first_name + ' ' + (member.last_name || '')"
              @click="select(member)"
            >
              <Icon v-if="isDead(member)" icon="mdi:skull" class="node-icon" />
              {{ member.first_name }} {{ member.last_name }}
            </button>
          </div>
        </div>
      </section>

      <div class="trunk" aria-hidden="true" />

      <section class="tier" aria-label="Children">
        <span class="tier-caption">Children</span>
        <div class="tier-nodes bus">
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
      </section>
    </div>

    <div v-else class="family-tree-empty">No lineage data.</div>
  </div>
</template>

<style scoped>
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
  background: color-mix(in srgb, var(--color-theme-primary) 18%, transparent);
}

.tree-refresh:disabled {
  opacity: 0.4;
  cursor: default;
}

.family-tree {
  display: flex;
  flex-direction: column;
  align-items: stretch;
}

.tier {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.tier-caption {
  font-size: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  color: var(--color-theme-primary);
  opacity: 0.6;
}

.tier-nodes {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;
  gap: 0.5rem;
}

.tier-nodes-column {
  flex-direction: column;
  align-items: stretch;
}

.bus {
  position: relative;
  width: fit-content;
  max-width: 100%;
  margin-inline: auto;
  padding-top: 0.65rem;
}

.bus::before {
  content: '';
  position: absolute;
  top: 0;
  left: 4px;
  right: 4px;
  height: 1px;
  background: var(--color-theme-primary);
  opacity: 0.55;
  box-shadow: 0 0 6px var(--color-theme-glow);
}

.bus:has(> :only-child)::before {
  display: none;
}

.trunk {
  width: 1px;
  height: 0.9rem;
  margin: 0.15rem auto;
  background: var(--color-theme-primary);
  opacity: 0.55;
  box-shadow: 0 0 6px var(--color-theme-glow);
}

.pair {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;
  gap: 0.5rem;
}

.siblings {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;
  gap: 0.5rem;
  border-top: 1px dashed color-mix(in srgb, var(--color-theme-primary) 35%, transparent);
  padding-top: 0.6rem;
}

.siblings-caption {
  font-size: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--color-theme-primary);
  opacity: 0.55;
}

.tree-node-sibling {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
}

.tree-node {
  background: color-mix(in srgb, var(--color-theme-primary) 8%, transparent);
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
  background: color-mix(in srgb, var(--color-theme-primary) 18%, transparent);
}

.tree-node-self {
  cursor: default;
  opacity: 0.85;
  background: color-mix(in srgb, var(--color-theme-primary) 20%, transparent);
}

.tree-node-partner {
  background: color-mix(in srgb, var(--color-theme-primary) 14%, transparent);
}

.pair-bond {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--color-theme-primary);
  background: rgba(0, 0, 0, 0.85);
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 45%, transparent);
  border-radius: 999px;
  padding: 0.15rem 0.65rem;
  white-space: nowrap;
}

.bond-affinity {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  opacity: 0.9;
}

.tree-node-dead {
  opacity: 0.5;
  text-decoration: line-through;
}

.node-icon {
  font-size: 0.875rem;
  opacity: 0.8;
}

.affinity-bar {
  width: 2rem;
  height: 3px;
  border-radius: 2px;
  background: color-mix(in srgb, var(--color-theme-primary) 25%, transparent);
  overflow: hidden;
}

.affinity-fill {
  display: block;
  height: 100%;
  background: var(--color-theme-primary);
  box-shadow: 0 0 4px var(--color-theme-glow);
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
  color: var(--color-danger);
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
  background: color-mix(in srgb, var(--color-theme-primary) 18%, transparent);
}
</style>

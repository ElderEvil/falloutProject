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

const isDead = (member: LineageMember) => member.is_dead
const partnerStage = (member: LineageMember) => member.relationship_type ?? 'partner'

const ageLabel = (age: string) => age.charAt(0).toUpperCase() + age.slice(1)


const selfAge = computed(() => {
  const age = ctx.dweller.value?.age_group
  return age ? ageLabel(age) : ''
})
</script>

<template>
  <div class="family-tree-panel">
    <div class="family-tree-header">
      <span v-if="lineage" class="tree-generation">Gen {{ lineage.generation }}</span>
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
            @click="select(member)"
          >
            <span class="member-info">
              <span class="member-name">
                <Icon v-if="isDead(member)" icon="mdi:skull" class="node-icon" />
                {{ member.first_name }} {{ member.last_name }}
              </span>
              <span class="member-age">{{ ageLabel(member.age_group) }}</span>
            </span>
          </button>
          <span v-if="!lineage.parents.length" class="tree-empty">—</span>
        </div>
      </section>

      <div class="trunk" aria-hidden="true" />

      <section class="tier" aria-label="Dweller">
        <span class="tier-caption">Dweller</span>
        <div class="tier-nodes tier-nodes-column">
          <div class="couple bus">
            <div class="member-card member-card-self">
              <span class="member-info">
                <span class="tree-node-self">{{ dwellerName || 'This Dweller' }}</span>
                <span v-if="selfAge" class="member-age">{{ selfAge }}</span>
              </span>
            </div>
            <template v-for="member in lineage.partners" :key="member.id">
              <span class="pair-bond" aria-hidden="true">
                <Icon
                  :icon="member.relationship_type === 'MARRIED' ? 'mdi:ring' : 'mdi:heart'"
                  class="node-icon"
                />
              </span>
              <button
                type="button"
                class="tree-node tree-node-partner"
                :class="{ 'tree-node-dead': isDead(member) }"
                @click="select(member)"
              >
                <span class="member-info">
                  <span class="member-name">
                <Icon v-if="isDead(member)" icon="mdi:skull" class="node-icon" />
                {{ member.first_name }} {{ member.last_name }}
              </span>
                  <span class="member-age">{{ ageLabel(member.age_group) }}</span>
                  <span class="member-relation">
                    {{ partnerStage(member) }}
                    <span v-if="member.affinity != null" class="bond-affinity">
                      <span class="affinity-bar" aria-hidden="true">
                        <span class="affinity-fill" :style="{ width: member.affinity + '%' }" />
                      </span>
                      {{ member.affinity }}♥
                    </span>
                  </span>
                </span>
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
              @click="select(member)"
            >
              <span class="member-info">
                <span class="member-name">
                <Icon v-if="isDead(member)" icon="mdi:skull" class="node-icon" />
                {{ member.first_name }} {{ member.last_name }}
              </span>
                <span class="member-age">{{ ageLabel(member.age_group) }}</span>
              </span>
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
            @click="select(member)"
          >
            <span class="member-info">
              <span class="member-name">
                <Icon v-if="isDead(member)" icon="mdi:skull" class="node-icon" />
                {{ member.first_name }} {{ member.last_name }}
              </span>
              <span class="member-age">{{ ageLabel(member.age_group) }}</span>
            </span>
          </button>
          <span v-if="!lineage.children.length" class="tree-empty">—</span>
        </div>
      </section>
    </div>

    <div v-else class="family-tree-empty">No lineage data.</div>
  </div>
</template>

<style scoped>
.family-tree-header {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.tree-generation {
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
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
  height: 2px;
  border-radius: var(--border-radius-full);
  background: var(--color-theme-primary);
  opacity: 0.55;
  box-shadow: 0 0 6px var(--color-theme-glow);
}

.bus:has(> :only-child)::before {
  display: none;
}

.trunk {
  width: 2px;
  height: 0.9rem;
  margin: 0.15rem auto;
  border-radius: var(--border-radius-full);
  background: var(--color-theme-primary);
  opacity: 0.55;
  box-shadow: 0 0 6px var(--color-theme-glow);
}

.couple {
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

.tree-node {
  background: color-mix(in srgb, var(--color-theme-primary) 8%, transparent);
  border: 1px solid var(--color-theme-primary);
  border-radius: var(--border-radius-base);
  padding: 0.5rem 0.6rem;
  color: var(--color-theme-primary);
  cursor: pointer;
  transition: all 0.2s;
  font-family: 'Courier New', monospace;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  min-width: 5.5rem;
  text-align: center;
}

.tree-node:hover {
  box-shadow: 0 0 12px var(--color-theme-glow);
  background: color-mix(in srgb, var(--color-theme-primary) 18%, transparent);
}

.tree-node:focus-visible {
  outline: 1px solid var(--color-theme-accent);
  outline-offset: 2px;
}

.tree-node-partner {
  background: color-mix(in srgb, var(--color-theme-primary) 14%, transparent);
}

.member-card {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  min-width: 5.5rem;
  padding: 0.5rem 0.6rem;
  border-radius: var(--border-radius-base);
  font-family: 'Courier New', monospace;
  color: var(--color-theme-primary);
  text-align: center;
}

.member-card-self {
  border: 1px solid var(--color-theme-accent);
  background: color-mix(in srgb, var(--color-theme-accent) 14%, transparent);
  box-shadow: 0 0 10px var(--color-theme-glow);
}


.member-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.1rem;
  line-height: 1.2;
}

.member-name,
.tree-node-self {
  font-size: 0.75rem;
  font-weight: 700;
}

.member-age {
  font-size: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  opacity: 0.65;
}

.member-relation {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  opacity: 0.85;
  margin-top: 0.15rem;
}

.pair-bond {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  border-radius: var(--border-radius-full);
  color: var(--color-theme-primary);
  background: var(--color-surface-sunken);
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 45%, transparent);
  flex-shrink: 0;
}

.bond-affinity {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  opacity: 0.9;
}

.tree-node-dead {
  opacity: 0.5;
}

.tree-node-dead .member-name {
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
  border-radius: var(--border-radius-base);
  color: var(--color-theme-primary);
  padding: 0.375rem 1rem;
  cursor: pointer;
}

.tree-retry:hover {
  background: color-mix(in srgb, var(--color-theme-primary) 18%, transparent);
}
</style>

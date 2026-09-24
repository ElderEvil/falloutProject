<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { humanizeSlug } from '../models/quest'
import type { QuestRequirement } from '../models/quest'

const props = defineProps<{
  requirements: QuestRequirement[]
  isMet: (req: QuestRequirement) => boolean
}>()

const questStore = useQuestStore()

function getRequirementCount(requirementData: Record<string, unknown>): number {
  const count = requirementData.count
  return typeof count === 'number' ? count : 0
}

function roomDisplayName(requirementData: Record<string, unknown>): string {
  const slug = requirementData.room_type
  if (typeof slug !== 'string' || slug.length === 0) return 'room'
  return slug
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function questRequirementName(requirementData: Record<string, unknown>): string {
  if (typeof requirementData.quest_name === 'string' && requirementData.quest_name.length > 0) {
    return requirementData.quest_name
  }
  if (typeof requirementData.quest_id === 'string') {
    const found
      = questStore.vaultQuests.find((q) => q.id === requirementData.quest_id)
        ?? questStore.quests.find((q) => q.id === requirementData.quest_id)
    if (found?.title) return found.title
  }
  return 'Previous quest'
}

function requirementIcon(req: QuestRequirement): string {
  if (!props.isMet(req)) return 'mdi:lock'
  return req.requirement_type === 'level' || req.requirement_type === 'quest_completed'
    ? 'mdi:lock-open'
    : 'mdi:check-circle'
}
</script>

<template>
  <div class="quest-section">
    <div class="section-label">
      <Icon icon="mdi:clipboard-check" class="inline-icon" />
      REQUIREMENTS
    </div>
    <ul class="prerequisites-list">
      <li
        v-for="req in requirements"
        :key="req.id"
        class="prerequisite-item"
        :class="{ met: isMet(req), unmet: !isMet(req) }"
      >
        <Icon :icon="requirementIcon(req)" class="prerequisite-icon" />
        <span class="prerequisite-text">
          <template v-if="req.requirement_type === 'level' && req.requirement_data">
            Requires Level {{ req.requirement_data.level || 1 }}+ dweller
            <span v-if="getRequirementCount(req.requirement_data) > 1">
              (x{{ getRequirementCount(req.requirement_data) }})
            </span>
          </template>
          <template v-else-if="req.requirement_type === 'item' && req.requirement_data">
            Requires {{ req.requirement_data.item_name || req.requirement_data.name || req.requirement_data.item_id }}
            <span v-if="getRequirementCount(req.requirement_data) > 1">
              (x{{ getRequirementCount(req.requirement_data) }})
            </span>
          </template>
          <template v-else-if="req.requirement_type === 'attack' && req.requirement_data">
            Requires {{ req.requirement_data.attack || 1 }}+ Attack
            <span v-if="getRequirementCount(req.requirement_data) > 1">
              (x{{ getRequirementCount(req.requirement_data) }})
            </span>
          </template>
          <template v-else-if="req.requirement_type === 'stat' && req.requirement_data">
            Requires {{ req.requirement_data.value || 1 }}+ {{ humanizeSlug(req.requirement_data.stat) }}
            <span v-if="getRequirementCount(req.requirement_data) > 1">
              (x{{ getRequirementCount(req.requirement_data) }})
            </span>
          </template>
          <template v-else-if="req.requirement_type === 'room' && req.requirement_data">
            Build {{ getRequirementCount(req.requirement_data) || 1 }} {{ roomDisplayName(req.requirement_data) }}
          </template>
          <template v-else-if="req.requirement_type === 'dweller_count' && req.requirement_data">
            Reach {{ getRequirementCount(req.requirement_data) }} dwellers
          </template>
          <template v-else-if="req.requirement_type === 'quest_completed' && req.requirement_data">
            Complete: {{ questRequirementName(req.requirement_data) }}
          </template>
          <template v-else>
            {{ humanizeSlug(req.requirement_type) }}
          </template>
        </span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.quest-section {
  margin-bottom: 12px;
}

.section-label {
  font-size: 0.75rem;
  font-weight: bold;
  color: var(--color-theme-accent);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.prerequisites-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.prerequisite-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 0.9rem;
}

.prerequisite-item.met {
  color: var(--color-theme-primary);
}

.prerequisite-item.unmet {
  color: var(--color-quest-muted);
}

.prerequisite-icon {
  font-size: 1rem;
}

.prerequisite-item.met .prerequisite-icon {
  color: var(--color-theme-primary);
}

.prerequisite-item.unmet .prerequisite-icon {
  color: var(--color-quest-locked);
}

.inline-icon {
  display: inline;
  vertical-align: middle;
}
</style>

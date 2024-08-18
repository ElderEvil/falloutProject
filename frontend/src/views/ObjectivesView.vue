<script setup lang="ts">
import { onMounted } from 'vue'
import { useObjectivesStore } from '@/stores/objectives'

const vaultId = localStorage.getItem('selectedVaultId') // Assuming vaultId is stored in localStorage
const objectivesStore = useObjectivesStore()

onMounted(() => {
  if (vaultId) {
    objectivesStore.fetchObjectives(vaultId)
  }
})

const markAsComplete = async (objectiveId: string) => {
  if (vaultId) {
    await objectivesStore.completeObjective(vaultId, objectiveId)
  }
}
</script>

<template>
  <div>
    <h1>Objectives</h1>
    <ul>
      <li v-for="objective in objectivesStore.objectives" :key="objective.id">
        {{ objective.name }}
        <button @click="markAsComplete(objective.id)">Complete</button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
/* Add styles as needed */
</style>

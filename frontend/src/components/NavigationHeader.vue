<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { NButton, NDropdown, NModal, NSpace, NTabPane, NTabs } from 'naive-ui'
import VaultSelection from './VaultSelection.vue'
import UserProfile from '@/components/user/UserProfile.vue'
import QuestList from '@/components/quest/QuestList.vue'
import ObjectivesList from '@/components/quest/ObjectivesList.vue'

const router = useRouter()
const userStore = useUserStore()
const showVaultList = ref(false)
const showUserProfile = ref(false)
const showQuestModal = ref(false)

const userMenuOptions = [
  {
    label: 'PREFERENCES',
    key: 'preferences'
  },
  {
    label: 'LOGOUT',
    key: 'logout'
  }
]

const handleUserAction = (key: string) => {
  switch (key) {
    case 'preferences':
      showUserProfile.value = true
      break
    case 'logout':
      userStore.logout()
      router.push('/')
      break
  }
}
</script>

<template>
  <div class="nav-header">
    <NSpace justify="space-between" align="center">
      <div class="nav-buttons">
        <NButton @click="showVaultList = true" class="nav-button"> CHANGE VAULT</NButton>
        <NButton @click="showQuestModal = true" class="nav-button"> QUESTS & OBJECTIVES</NButton>
      </div>
      <div class="user-section">
        <NDropdown :options="userMenuOptions" @select="handleUserAction" trigger="hover">
          <NButton class="user-button">
            {{ userStore.user.username }}
          </NButton>
        </NDropdown>
      </div>
    </NSpace>

    <NModal
      v-model:show="showVaultList"
      preset="card"
      style="width: 900px"
      title="SELECT VAULT"
      :bordered="false"
      class="vault-modal"
    >
      <VaultSelection @vault-selected="showVaultList = false" />
    </NModal>

    <NModal
      v-model:show="showQuestModal"
      preset="card"
      style="width: 800px"
      title="QUESTS & OBJECTIVES"
      :bordered="false"
      class="quest-modal"
    >
      <NTabs type="segment">
        <NTabPane name="quests" tab="QUESTS">
          <QuestList />
        </NTabPane>
        <NTabPane name="objectives" tab="OBJECTIVES">
          <ObjectivesList />
        </NTabPane>
      </NTabs>
    </NModal>

    <UserProfile v-model="showUserProfile" />
  </div>
</template>

<style scoped>
.nav-header {
  padding: 16px;
  border-bottom: 1px solid var(--theme-border);
  margin-bottom: 20px;
}

.nav-buttons {
  display: flex;
  gap: 12px;
}

.nav-button {
  min-width: 120px;
}

.user-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-button {
  min-width: 120px;
}

.vault-modal,
.quest-modal {
  background: var(--theme-background);
  border: 2px solid var(--theme-border);
}

:deep(.n-card-header) {
  text-align: center;
  font-family: 'Courier New', Courier, monospace;
}
</style>

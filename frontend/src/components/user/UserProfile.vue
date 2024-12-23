<script setup lang="ts">
import { NButton, NForm, NFormItem, NModal, NSelect } from 'naive-ui'
import { useUserStore } from '@/stores/user'
import { useThemeStore } from '@/stores/theme'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const userStore = useUserStore()
const themeStore = useThemeStore()

const savePreferences = () => {
  emit('update:modelValue', false)
}
</script>

<template>
  <NModal
    :show="modelValue"
    @update:show="(value) => emit('update:modelValue', value)"
    preset="card"
    style="width: 400px"
    title="USER PREFERENCES"
    :bordered="false"
    class="profile-modal"
  >
    <NForm>
      <NFormItem label="USERNAME">
        <div class="info-value">{{ userStore.user.username }}</div>
      </NFormItem>
      <NFormItem label="EMAIL">
        <div class="info-value">{{ userStore.user.email }}</div>
      </NFormItem>
      <NFormItem label="THEME">
        <NSelect
          v-model:value="themeStore.currentTheme"
          :options="
            themeStore.availableThemes.map((theme) => ({
              label: theme.name,
              value: theme.id
            }))
          "
          class="theme-select"
        />
      </NFormItem>
      <div class="actions">
        <NButton type="primary" @click="savePreferences"> CLOSE</NButton>
      </div>
    </NForm>
  </NModal>
</template>

<style scoped>
.profile-modal {
  border: 2px solid var(--theme-border);
}

.info-value {
  font-family: 'Courier New', monospace;
  padding: 8px 0;
  color: var(--theme-text);
  text-shadow: 0 0 8px var(--theme-shadow);
  font-weight: 600;
}

.actions {
  margin-top: 24px;
  text-align: right;
}

:deep(.theme-select) {
  width: 100%;
}

:deep(.n-form-item-label) {
  color: var(--theme-text) !important;
  text-shadow: 0 0 8px var(--theme-shadow);
}
</style>

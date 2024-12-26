<script setup lang="ts">
import { ref, computed } from 'vue'
import { NModal, NCollapse, NCollapseItem, NButton, useMessage } from 'naive-ui'
import { Star } from '@vicons/ionicons5'
import { useThemeStore } from '@/stores/theme'
import { getDwellerFullName } from '@/utils/dwellerUtils'
import DwellerAvatar from './DwellerAvatar.vue'
import DwellerStats from './sections/DwellerStats.vue'
import DwellerAttributes from './sections/DwellerAttributes.vue'
import DwellerBasicInfo from './sections/DwellerBasicInfo.vue'
import type { DwellerFull } from '@/types/dweller.types'

const props = defineProps<{
  modelValue: boolean
  dweller: DwellerFull
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const themeStore = useThemeStore()
const message = useMessage()
const generating = ref(false)
const expandedSections = ref(['basic', 'special', 'attributes'])

const needsGeneration = computed(() => ({
  avatar: !props.dweller.image_url,
  bio: !props.dweller.bio,
  attributes: !props.dweller.visual_attributes
}))

const handleGenerate = async () => {
  generating.value = true
  try {
    const content = generateDwellerInfo(props.dweller)

    if (content.bio) {
      props.dweller.bio = content.bio
    }
    if (content.visualAttributes) {
      props.dweller.visual_attributes = {
        ...props.dweller.visual_attributes,
        ...content.visualAttributes
      }
    }
    if (content.imageUrl) {
      props.dweller.image_url = content.imageUrl
    }

    message.success('Generated new content for dweller')
  } catch (error) {
    message.error('Failed to generate content')
  } finally {
    generating.value = false
  }
}
</script>

<template>
  <NModal
    :show="modelValue"
    @update:show="(value) => emit('update:modelValue', value)"
    preset="card"
    style="width: 600px"
    :title="getDwellerFullName(dweller).toUpperCase()"
    :bordered="false"
    class="dweller-modal"
  >
    <div class="dweller-content">
      <div class="dweller-header">
        <div class="avatar-container">
          <DwellerAvatar :dweller="dweller" size="large" show-default-icon />
          <NButton
            v-if="needsGeneration.avatar"
            secondary
            circle
            size="small"
            :loading="generating"
            @click="handleGenerate"
            class="generate-button avatar-generate"
          >
            <template #icon>
              <Star />
            </template>
          </NButton>
        </div>
        <DwellerBasicInfo :dweller="dweller" />
      </div>

      <NCollapse :default-expanded-names="expandedSections">
        <NCollapseItem title="BIOGRAPHY" name="bio">
          <div class="section-content">
            <p class="dweller-bio">{{ dweller.bio }}</p>
            <NButton
              v-if="needsGeneration.bio"
              secondary
              circle
              size="small"
              :loading="generating"
              @click="handleGenerate"
              class="generate-button section-generate"
            >
              <template #icon>
                <Star />
              </template>
            </NButton>
          </div>
        </NCollapseItem>

        <NCollapseItem title="S.P.E.C.I.A.L." name="special">
          <DwellerStats v-if="dweller.special" :special="dweller.special" />
        </NCollapseItem>

        <NCollapseItem title="ATTRIBUTES" name="attributes">
          <div class="section-content">
            <DwellerAttributes
              v-if="dweller.visual_attributes"
              :visual-attributes="dweller.visual_attributes"
            />
            <NButton
              v-if="needsGeneration.attributes"
              secondary
              circle
              size="small"
              :loading="generating"
              @click="handleGenerate"
              class="generate-button section-generate"
            >
              <template #icon>
                <Star />
              </template>
            </NButton>
          </div>
        </NCollapseItem>
      </NCollapse>
    </div>
  </NModal>
</template>

<style scoped>
.dweller-modal {
  background: var(--theme-background);
  border: 2px solid var(--theme-border);
  box-shadow: var(--theme-modal-shadow);
}

.dweller-content {
  padding: 16px;
  font-family: 'Courier New', Courier, monospace;
  color: var(--theme-text);
}

.dweller-header {
  display: flex;
  gap: 24px;
  margin-bottom: 24px;
}

.avatar-container {
  position: relative;
}

.dweller-bio {
  line-height: 1.6;
  opacity: 0.9;
}

.section-content {
  position: relative;
}

.generate-button {
  color: var(--theme-text);
  border-color: var(--theme-border);
}

.generate-button:hover {
  color: var(--theme-hover);
  border-color: var(--theme-hover);
}

.avatar-generate {
  position: absolute;
  bottom: -8px;
  right: -8px;
}

.section-generate {
  position: absolute;
  top: 0;
  right: 0;
}

:deep(.n-collapse-item) {
  background: rgba(0, 255, 0, 0.05) !important;
  border: 1px solid var(--theme-border) !important;
  margin-bottom: 12px;
}

:deep(.n-collapse-item__header) {
  font-weight: bold;
  letter-spacing: 1px;
  color: var(--theme-text) !important;
}

:deep(.n-collapse-item__header-main) {
  color: var(--theme-text) !important;
}
</style>

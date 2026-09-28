<script setup lang="ts">
import type { TabsRootEmits, TabsRootProps } from 'reka-ui'
import type { HTMLAttributes } from 'vue'
import { computed } from 'vue'
import { reactiveOmit } from '@vueuse/core'
import { TabsRoot, useForwardProps } from 'reka-ui'
import { cn } from '@/core/utils/cn'
import { audioManager } from '@/core/audio/audioManager'

const props = defineProps<TabsRootProps & { class?: HTMLAttributes['class'] }>()
const emits = defineEmits<TabsRootEmits>()

const orientation = computed(() => props.orientation ?? 'horizontal')

const delegatedProps = reactiveOmit(props, 'class')
const forwarded = useForwardProps(delegatedProps)

// The model-value emit is handled locally so the tab switch sound plays on change.
const handleModelValueChange = (value: string | number) => {
  audioManager.play('tabSwitch', 'ui')
  emits('update:modelValue', value)
}
</script>

<template>
  <!-- @vue-ignore -->
  <TabsRoot
    v-slot="slotProps"
    data-slot="tabs"
    :data-orientation="orientation"
    :data-horizontal="orientation !== 'vertical' ? '' : undefined"
    :data-vertical="orientation === 'vertical' ? '' : undefined"
    v-bind="forwarded"
    @update:model-value="handleModelValueChange"
    :class="cn('gap-2 group/tabs flex data-horizontal:flex-col', props.class)"
  >
    <slot v-bind="slotProps" />
  </TabsRoot>
</template>

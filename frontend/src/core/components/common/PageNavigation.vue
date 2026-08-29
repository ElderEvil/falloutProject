<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'
import { Icon } from '@iconify/vue'
import { RouterLink, useRouter } from 'vue-router'
import BackButton from '@/core/components/common/BackButton.vue'
import { useGoBack } from '@/core/composables/useGoBack'

interface BreadcrumbItem {
  label: string
  to?: RouteLocationRaw
}

const props = withDefaults(
  defineProps<{
    breadcrumbs: BreadcrumbItem[]
    backLabel?: string
    backTo?: RouteLocationRaw
  }>(),
  { backLabel: 'Back' }
)

const router = useRouter()
const { goBack } = useGoBack()

function navigateBack(): void {
  if (props.backTo) {
    void router.push(props.backTo)
    return
  }
  goBack()
}
</script>

<template>
  <div class="mb-4 flex flex-wrap items-center gap-x-3 gap-y-2">
    <BackButton :label="backLabel" @click="navigateBack" />

    <nav v-if="breadcrumbs.length" aria-label="Breadcrumb">
      <ol class="flex flex-wrap items-center gap-1.5 text-xs font-bold tracking-[0.1em] text-theme-primary/60">
        <li v-for="(breadcrumb, index) in breadcrumbs" :key="breadcrumb.label" class="flex items-center gap-1.5">
          <Icon
            v-if="index > 0"
            icon="mdi:chevron-right"
            class="h-3.5 w-3.5 text-theme-primary/35"
            :ariaHidden="true"
          />
          <RouterLink
            v-if="breadcrumb.to"
            :to="breadcrumb.to"
            class="transition-colors hover:text-theme-primary focus-visible:outline-2 focus-visible:outline-dashed focus-visible:outline-offset-2 focus-visible:outline-theme-primary"
          >
            {{ breadcrumb.label }}
          </RouterLink>
          <span v-else aria-current="page" class="text-theme-primary">{{ breadcrumb.label }}</span>
        </li>
      </ol>
    </nav>
  </div>
</template>

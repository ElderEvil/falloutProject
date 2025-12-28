<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const menuItems = [
  [
    {
      label: 'QUESTS',
      icon: 'i-lucide-clipboard-list',
      badge: '3',
      click: () => console.log('Quests coming soon')
    },
    {
      label: 'OBJECTIVES',
      icon: 'i-lucide-flag',
      badge: '5',
      click: () => router.push('/objectives')
    }
  ],
  [
    {
      label: 'STATISTICS',
      icon: 'i-lucide-bar-chart',
      click: () => console.log('Statistics coming soon')
    },
    {
      label: 'ACHIEVEMENTS',
      icon: 'i-lucide-trophy',
      click: () => console.log('Achievements coming soon')
    }
  ],
  [
    {
      label: 'HELP',
      icon: 'i-lucide-help-circle',
      click: () => console.log('Help coming soon')
    }
  ]
]
</script>

<template>
  <UDropdown
    :items="menuItems"
    :ui="{
      item: {
        base: 'text-primary-500 uppercase',
        active: 'bg-primary-950'
      },
      background: 'bg-black border-2 border-primary-600'
    }"
    :popper="{ placement: 'bottom-end' }"
  >
    <UButton
      color="primary"
      variant="outline"
      size="lg"
      icon="i-lucide-monitor"
      class="uppercase font-bold"
    >
      PIP-BOY
    </UButton>

    <template #item="{ item }">
      <div class="flex items-center justify-between w-full">
        <div class="flex items-center space-x-2">
          <UIcon :name="item.icon" class="h-5 w-5" />
          <span>{{ item.label }}</span>
        </div>
        <UBadge
          v-if="item.badge"
          color="primary"
          variant="solid"
          size="xs"
        >
          {{ item.badge }}
        </UBadge>
      </div>
    </template>
  </UDropdown>
</template>

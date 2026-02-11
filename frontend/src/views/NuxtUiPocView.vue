<script setup lang="ts">
import { ref } from 'vue'
import { useTheme } from '@/core/composables/useTheme'
import { useVisualEffects } from '@/core/composables/useVisualEffects'
import { UCard as CustomCard, UButton as CustomButton, UBadge as CustomBadge } from '@/core/components/ui'

const { currentTheme, setTheme, availableThemes } = useTheme()
const { flickering, toggleFlickering } = useVisualEffects()

// Component comparison state
const activeTab = ref('comparison')
const buttonLoading = ref(false)
const modalOpen = ref(false)
const alertVisible = ref(true)

function triggerLoading() {
  buttonLoading.value = true
  setTimeout(() => buttonLoading.value = false, 2000)
}
</script>

<template>
  <div class="min-h-screen bg-black p-6 font-mono">
    <div class="max-w-6xl mx-auto">
      <!-- Header -->
      <div class="mb-8">
        <h1 
          class="text-3xl font-bold mb-2"
          :style="{ color: 'var(--color-theme-primary)' }"
        >
          Nuxt UI Integration POC
        </h1>
        <p class="text-gray-400">
          Testing Nuxt UI components with your existing theme system
        </p>
      </div>

      <!-- Theme Switcher (Works with both!) -->
      <CustomCard class="mb-8" title="Theme Switcher" glow>
        <p class="mb-4 text-sm text-gray-400">
          Current: <span :style="{ color: currentTheme.colors.primary }">{{ currentTheme.displayName }}</span>
        </p>
        <div class="flex gap-3 flex-wrap">
          <button
            v-for="theme in availableThemes"
            :key="theme.name"
            @click="setTheme(theme.name)"
            class="px-4 py-2 border-2 rounded transition-all"
            :class="{ 
              'opacity-100': currentTheme.name === theme.name,
              'opacity-60': currentTheme.name !== theme.name 
            }"
            :style="{
              borderColor: theme.colors.primary,
              color: theme.colors.primary,
              boxShadow: currentTheme.name === theme.name ? `0 0 15px ${theme.colors.glow}` : 'none'
            }"
          >
            {{ theme.name.toUpperCase() }}
          </button>
        </div>
        <p class="mt-4 text-xs text-gray-500">
          All components below should update when you switch themes ↑
        </p>
      </CustomCard>

      <!-- Tabs -->
      <div class="flex gap-4 mb-6 border-b border-gray-800 pb-2">
        <button
          v-for="tab in ['comparison', 'native-nuxt', 'your-custom']"
          :key="tab"
          @click="activeTab = tab"
          class="px-4 py-2 transition-colors"
          :class="{ 
            'border-b-2': activeTab === tab,
            'text-gray-400': activeTab !== tab 
          }"
          :style="{ 
            color: activeTab === tab ? 'var(--color-theme-primary)' : undefined,
            borderColor: activeTab === tab ? 'var(--color-theme-primary)' : undefined
          }"
        >
          {{ tab === 'comparison' ? 'Side-by-Side' : tab === 'native-nuxt' ? 'Native Nuxt UI' : 'Your Custom' }}
        </button>
      </div>

      <!-- Side-by-Side Comparison -->
      <div v-if="activeTab === 'comparison'" class="grid md:grid-cols-2 gap-8">
        <!-- Native Nuxt UI -->
        <CustomCard title="Native Nuxt UI" glow>
          <p class="text-xs text-gray-500 mb-4">
            These use Nuxt UI components directly (UButton, UBadge, UAlert)
          </p>
          
          <div class="space-y-4">
            <div class="flex gap-2 flex-wrap">
              <UButton>Default</UButton>
              <UButton color="primary">Primary</UButton>
              <UButton color="secondary">Secondary</UButton>
              <UButton variant="outline">Outline</UButton>
            </div>

            <div class="flex gap-2">
              <UBadge>Default</UBadge>
              <UBadge color="primary">Primary</UBadge>
              <UBadge color="success">Success</UBadge>
              <UBadge color="warning">Warning</UBadge>
              <UBadge color="error">Error</UBadge>
            </div>

            <UAlert
              v-if="alertVisible"
              title="Nuxt UI Alert"
              color="primary"
              close
              @close="alertVisible = false"
            >
              This is a native Nuxt UI alert component
            </UAlert>
            <CustomButton v-else @click="alertVisible = true" size="sm">
              Show Alert Again
            </CustomButton>

            <UButton @click="modalOpen = true" variant="outline">
              Open Nuxt UI Modal
            </UButton>

            <USkeleton class="h-4 w-full" />
            <USkeleton class="h-4 w-3/4" />
          </div>
        </CustomCard>

        <!-- Your Custom Components -->
        <CustomCard title="Your Custom Components" glow>
          <p class="text-xs text-gray-500 mb-4">
            These use your current custom UI components
          </p>
          
          <div class="space-y-4">
            <div class="flex gap-2 flex-wrap">
              <CustomButton>Default</CustomButton>
              <CustomButton variant="primary">Primary</CustomButton>
              <CustomButton variant="secondary">Secondary</CustomButton>
              <CustomButton variant="ghost">Ghost</CustomButton>
            </div>

            <div class="flex gap-2">
              <CustomBadge>Default</CustomBadge>
              <CustomBadge variant="success">Success</CustomBadge>
              <CustomBadge variant="warning">Warning</CustomBadge>
              <CustomBadge variant="danger">Danger</CustomBadge>
            </div>

            <div 
              class="p-4 rounded border"
              :style="{ borderColor: 'var(--color-theme-primary)', color: 'var(--color-theme-primary)' }"
            >
              <strong>Custom Alert:</strong> This uses your existing alert styling
            </div>

            <CustomButton @click="triggerLoading" :loading="buttonLoading">
              {{ buttonLoading ? 'Loading...' : 'Test Loading State' }}
            </CustomButton>

            <CustomButton @click="toggleFlickering" :variant="flickering ? 'primary' : 'secondary'">
              {{ flickering ? 'Disable' : 'Enable' }} Flickering
            </CustomButton>
          </div>
        </CustomCard>
      </div>

      <!-- Native Nuxt UI Only -->
      <div v-else-if="activeTab === 'native-nuxt'" class="space-y-6">
        <CustomCard title="Buttons" glow>
          <div class="flex gap-2 flex-wrap">
            <UButton>Default</UButton>
            <UButton color="primary">Primary</UButton>
            <UButton color="secondary">Secondary</UButton>
            <UButton color="success">Success</UButton>
            <UButton color="warning">Warning</UButton>
            <UButton color="error">Error</UButton>
            <UButton color="neutral">Neutral</UButton>
          </div>
          <div class="flex gap-2 flex-wrap mt-4">
            <UButton variant="solid">Solid</UButton>
            <UButton variant="outline">Outline</UButton>
            <UButton variant="soft">Soft</UButton>
            <UButton variant="ghost">Ghost</UButton>
            <UButton variant="link">Link</UButton>
          </div>
        </CustomCard>

        <CustomCard title="Badges" glow>
          <div class="flex gap-2 flex-wrap">
            <UBadge>Default</UBadge>
            <UBadge color="primary">Primary</UBadge>
            <UBadge color="secondary">Secondary</UBadge>
            <UBadge color="success">Success</UBadge>
            <UBadge color="warning">Warning</UBadge>
            <UBadge color="error">Error</UBadge>
            <UBadge color="neutral">Neutral</UBadge>
          </div>
          <div class="flex gap-2 flex-wrap mt-4">
            <UBadge variant="solid">Solid</UBadge>
            <UBadge variant="outline">Outline</UBadge>
            <UBadge variant="soft">Soft</UBadge>
            <UBadge variant="subtle">Subtle</UBadge>
          </div>
        </CustomCard>

        <CustomCard title="Alerts" glow>
          <UAlert title="Primary Alert" color="primary" class="mb-2">
            This is a primary colored alert
          </UAlert>
          <UAlert title="Success Alert" color="success" variant="subtle" class="mb-2">
            This is a success alert with subtle variant
          </UAlert>
          <UAlert title="Warning Alert" color="warning" variant="outline" class="mb-2">
            This is a warning alert with outline variant
          </UAlert>
          <UAlert title="Error Alert" color="error" variant="soft">
            This is an error alert with soft variant
          </UAlert>
        </CustomCard>

        <CustomCard title="Skeleton Loading" glow>
          <div class="space-y-2">
            <USkeleton class="h-4 w-full" />
            <USkeleton class="h-4 w-5/6" />
            <USkeleton class="h-4 w-4/6" />
            <div class="flex gap-2 mt-4">
              <USkeleton class="h-12 w-12 rounded-full" />
              <div class="flex-1 space-y-2">
                <USkeleton class="h-4 w-full" />
                <USkeleton class="h-4 w-5/6" />
              </div>
            </div>
          </div>
        </CustomCard>
      </div>

      <!-- Your Custom Components Only -->
      <div v-else class="space-y-6">
        <CustomCard title="Your Current Button Components" glow>
          <div class="flex gap-2 flex-wrap">
            <CustomButton>Default</CustomButton>
            <CustomButton variant="primary">Primary</CustomButton>
            <CustomButton variant="secondary">Secondary</CustomButton>
            <CustomButton variant="danger">Danger</CustomButton>
            <CustomButton variant="ghost">Ghost</CustomButton>
          </div>
          <div class="flex gap-2 flex-wrap mt-4">
            <CustomButton size="xs">XS</CustomButton>
            <CustomButton size="sm">SM</CustomButton>
            <CustomButton size="md">MD</CustomButton>
            <CustomButton size="lg">LG</CustomButton>
            <CustomButton size="xl">XL</CustomButton>
          </div>
        </CustomCard>

        <CustomCard title="Your Current Badge Components" glow>
          <div class="flex gap-2 flex-wrap">
            <CustomBadge>Default</CustomBadge>
            <CustomBadge variant="success">Success</CustomBadge>
            <CustomBadge variant="warning">Warning</CustomBadge>
            <CustomBadge variant="danger">Danger</CustomBadge>
            <CustomBadge variant="info">Info</CustomBadge>
          </div>
        </CustomCard>
      </div>

      <!-- Modal -->
      <UModal v-model="modalOpen" title="Nuxt UI Modal Test">
        <p class="mb-4">
          This is a native Nuxt UI modal. Check if it respects your theme colors!
        </p>
        <p class="text-sm text-gray-500">
          The modal should have your theme color in the header and buttons.
        </p>
        <template #footer>
          <UButton @click="modalOpen = false" variant="outline">
            Cancel
          </UButton>
          <UButton @click="modalOpen = false" color="primary">
            Confirm
          </UButton>
        </template>
      </UModal>

      <!-- Footer Notes -->
      <div class="mt-12 p-4 border border-gray-800 rounded text-sm text-gray-500">
        <h3 class="font-bold mb-2" :style="{ color: 'var(--color-theme-primary)' }">
          Testing Checklist:
        </h3>
        <ul class="space-y-1 list-disc list-inside">
          <li>Switch themes (FO3/FNV/FO4) - all components should update</li>
          <li>Native Nuxt UI buttons should match your custom button colors</li>
          <li>Badges should use theme colors</li>
          <li>Modal should have theme-colored header</li>
          <li>If colors don't match, we need to configure Nuxt UI theme bridge</li>
        </ul>
      </div>
    </div>
  </div>
</template>

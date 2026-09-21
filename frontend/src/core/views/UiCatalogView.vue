<script setup lang="ts">
/**
 * UiCatalogView — dev-only regression catalog for the core UI primitives.
 *
 * Renders every component from `@/core/components/ui` in all variants, sizes
 * and relevant states so a Playwright aria snapshot + pixel screenshot can
 * prove the upcoming shadcn-vue swap is visually neutral. The imports below
 * are the invariant contract: they must keep pointing at `@/core/components/ui`
 * while the primitives' internals get replaced.
 *
 * Overlay primitives are rendered open/visible (never hover-dependent):
 * - UModal is open by default.
 * - UTooltip triggers are focused by the spec (focus, not hover).
 * - UToast fixtures are rendered inline; the global UToastContainer (mounted
 *   in App.vue) is populated on mount with duration-0 toasts.
 */
import { defineComponent, h, onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import {
  UAlert,
  UBadge,
  UButton,
  UCard,
  UIconButton,
  UInput,
  UModal,
  UProgressBar,
  USelect,
  USkeleton,
  USlider,
  UTabs,
  UTooltip,
} from '@/core/components/ui'
import UToast from '@/core/components/ui/UToast.vue'
import SettingItem from '@/core/components/ui/SettingItem.vue'
import { useToast, type Toast } from '@/core/composables/useToast'

// Icon components for the primitives' `icon` props (IconComponent = Component | string).
const CheckIcon = defineComponent({
  name: 'CheckIcon',
  render: () => h(Icon, { icon: 'mdi:check' }),
})
const AlertIcon = defineComponent({
  name: 'AlertIcon',
  render: () => h(Icon, { icon: 'mdi:alert' }),
})
const InfoIcon = defineComponent({
  name: 'InfoIcon',
  render: () => h(Icon, { icon: 'mdi:information' }),
})
const WrenchIcon = defineComponent({
  name: 'WrenchIcon',
  render: () => h(Icon, { icon: 'mdi:wrench' }),
})

// --- toast seeding: populate the global UToastContainer deterministically ---
const { toasts, remove, show } = useToast()
onMounted(() => {
  while (toasts.value.length > 0) remove(toasts.value[0]!.id)
  show('Vault saved successfully', 'success', 0)
  show('Radiation levels critical', 'error', 0)
  show('New dweller arrived', 'warning', 0)
  show('Quest completed', 'info', 0)
})

// --- static fixtures ---
const toastFixtures: Toast[] = [
  { id: 'toast-fixture-success', message: 'Direct UToast — success', variant: 'success' },
  { id: 'toast-fixture-error', message: 'Direct UToast — error', variant: 'error' },
  { id: 'toast-fixture-warning', message: 'Direct UToast — warning', variant: 'warning', count: 3 },
  { id: 'toast-fixture-info', message: 'Direct UToast — info', variant: 'info' },
]

const buttonVariants = ['primary', 'secondary', 'success', 'danger', 'ghost'] as const
const buttonSizes = ['xs', 'sm', 'md', 'lg', 'xl'] as const
const inputSizes = ['sm', 'md', 'lg'] as const
const badgeVariants = [
  'success',
  'warning',
  'danger',
  'info',
  'default',
  'primary',
  'secondary',
  'outline',
] as const
const badgeSizes = ['sm', 'md', 'lg'] as const
const cardPaddings = ['none', 'sm', 'md', 'lg', 'xl'] as const
const sliderAccents = ['primary', 'success', 'caps', 'danger'] as const
const skeletonRounded = ['none', 'sm', 'md', 'lg', 'full'] as const

const selectOptions = [
  { value: 'vault-1', label: 'Vault 101' },
  { value: 'vault-2', label: 'Vault 13' },
  { value: 'vault-3', label: 'Vault 111' },
]

const tabs = [
  { key: 'overview', label: 'Overview' },
  { key: 'dwellers', label: 'Dwellers', icon: 'mdi:account-group' },
  { key: 'disabled', label: 'Disabled', disabled: true },
  { key: 'storage', label: 'Storage' },
]

const modalOpen = ref(true)
const activeTab = ref('overview')
const selectValue = ref('vault-1')
const sliderValue = ref(50)
const inputValue = ref('')
</script>

<template>
  <div class="mx-auto max-w-6xl px-6 py-8">
    <h1 class="text-3xl font-bold terminal-glow text-theme-primary">UI Catalog</h1>
    <p class="mt-2 text-sm text-theme-primary/60">
      Dev-only regression catalog for the core UI primitives. Imports stay pinned to
      <code class="text-theme-primary">@/core/components/ui</code> so the shadcn-vue swap can be
      proven visually neutral against the Playwright baselines.
    </p>

    <!-- ============ UButton ============ -->
    <section class="mt-10" aria-labelledby="h-ubutton">
      <h2 id="h-ubutton" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        UButton
      </h2>
      <div class="flex flex-wrap items-center gap-3">
        <UButton v-for="variant in buttonVariants" :key="variant" :variant="variant">
          {{ variant }}
        </UButton>
      </div>
      <div class="mt-4 flex flex-wrap items-center gap-3">
        <UButton v-for="size in buttonSizes" :key="size" :size="size">Size {{ size }}</UButton>
      </div>
      <div class="mt-4 flex flex-wrap items-center gap-3">
        <UButton disabled>Disabled</UButton>
        <UButton loading>Loading</UButton>
        <UButton :icon="CheckIcon">With icon</UButton>
        <UButton :icon-right="WrenchIcon">Icon right</UButton>
        <UButton :icon="CheckIcon" :icon-right="WrenchIcon">Both icons</UButton>
        <UButton block class="w-48">Block</UButton>
      </div>
    </section>

    <!-- ============ UInput ============ -->
    <section class="mt-10" aria-labelledby="h-uinput">
      <h2 id="h-uinput" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        UInput
      </h2>
      <div class="grid max-w-2xl gap-4">
        <UInput v-model="inputValue" placeholder="Default input" />
        <UInput v-for="size in inputSizes" :key="size" v-model="inputValue" :size="size" :placeholder="`Size ${size}`" />
        <UInput v-model="inputValue" label="Dweller name" placeholder="e.g. Butch" required />
        <UInput v-model="inputValue" label="Caps" label-icon="mdi:currency-usd" placeholder="Amount" help-text="How many caps to deposit" />
        <UInput v-model="inputValue" label="Radiation" placeholder="Error state" error="Radiation exceeds safe levels" />
        <UInput v-model="inputValue" placeholder="Disabled input" disabled />
        <UInput v-model="inputValue" placeholder="With icon" :icon="CheckIcon" />
        <UInput v-model="inputValue" placeholder="With right icon" :icon-right="WrenchIcon" />
        <UInput v-model="inputValue" placeholder="Terminal variant" variant="terminal" />
        <UInput v-model="inputValue" type="password" placeholder="Password" />
      </div>
    </section>

    <!-- ============ UBadge ============ -->
    <section class="mt-10" aria-labelledby="h-ubadge">
      <h2 id="h-ubadge" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        UBadge
      </h2>
      <div class="flex flex-wrap items-center gap-3">
        <UBadge v-for="variant in badgeVariants" :key="variant" :variant="variant">{{ variant }}</UBadge>
      </div>
      <div class="mt-4 flex flex-wrap items-center gap-3">
        <UBadge v-for="size in badgeSizes" :key="size" :size="size">Size {{ size }}</UBadge>
      </div>
      <div class="mt-4 flex flex-wrap items-center gap-3">
        <UBadge variant="success" dot>Dot</UBadge>
        <UBadge variant="warning" dot>Dot</UBadge>
        <UBadge variant="danger" :icon="AlertIcon">With icon</UBadge>
        <UBadge variant="info" :icon="InfoIcon">With icon</UBadge>
      </div>
    </section>

    <!-- ============ UCard ============ -->
    <section class="mt-10" aria-labelledby="h-ucard">
      <h2 id="h-ucard" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        UCard
      </h2>
      <div class="grid gap-4 md:grid-cols-3">
        <UCard v-for="padding in cardPaddings" :key="padding" :padding="padding">
          <p class="text-sm text-theme-primary/80">Padding {{ padding }}</p>
        </UCard>
        <UCard title="Glow card" glow>
          <p class="text-sm text-theme-primary/80">Glow enabled</p>
        </UCard>
        <UCard title="CRT card" crt>
          <p class="text-sm text-theme-primary/80">CRT screen effect</p>
        </UCard>
        <UCard title="Unbordered" :bordered="false">
          <p class="text-sm text-theme-primary/80">No border</p>
        </UCard>
        <UCard title="Raised surface" surface="raised">
          <p class="text-sm text-theme-primary/80">Raised</p>
        </UCard>
        <UCard title="Sunken surface" surface="sunken">
          <p class="text-sm text-theme-primary/80">Sunken</p>
        </UCard>
        <UCard title="Slotted card">
          <template #header>
            <span class="text-sm font-bold text-theme-primary">Custom header</span>
          </template>
          <p class="text-sm text-theme-primary/80">Header + footer slots</p>
          <template #footer>
            <UButton size="sm">Footer action</UButton>
          </template>
        </UCard>
      </div>
    </section>

    <!-- ============ UAlert ============ -->
    <section class="mt-10" aria-labelledby="h-ualert">
      <h2 id="h-ualert" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        UAlert
      </h2>
      <div class="grid max-w-2xl gap-3">
        <UAlert variant="success" title="Success" :icon="CheckIcon">Vault created successfully</UAlert>
        <UAlert variant="warning" title="Warning" :icon="AlertIcon">Power reserves are low</UAlert>
        <UAlert variant="danger" title="Danger" :icon="AlertIcon">Radiation leak detected</UAlert>
        <UAlert variant="info" title="Info" :icon="InfoIcon">New dweller arrived</UAlert>
        <UAlert variant="success" dismissible>Dismissible alert</UAlert>
        <UAlert variant="info">Plain alert without title or icon</UAlert>
      </div>
    </section>

    <!-- ============ UModal ============ -->
    <section class="mt-10" aria-labelledby="h-umodal">
      <h2 id="h-umodal" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        UModal
      </h2>
      <p class="text-sm text-theme-primary/60">
        Rendered open (default size, title, body and footer) so capture is deterministic.
      </p>
      <UModal v-model="modalOpen" title="Confirm evacuation">
        <p class="text-sm text-theme-primary/80">
          Are you sure you want to evacuate this vault? All dwellers will be relocated.
        </p>
        <template #footer>
          <UButton variant="secondary">Cancel</UButton>
          <UButton variant="danger">Evacuate</UButton>
        </template>
      </UModal>
    </section>

    <!-- ============ UTabs ============ -->
    <section class="mt-10" aria-labelledby="h-utabs">
      <h2 id="h-utabs" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        UTabs
      </h2>
      <UTabs v-model="activeTab" :tabs="tabs">
        <template #default="{ activeTab: current }">
          <p class="text-sm text-theme-primary/80">Active tab: {{ current }}</p>
        </template>
      </UTabs>
    </section>

    <!-- ============ USelect ============ -->
    <section class="mt-10" aria-labelledby="h-uselect">
      <h2 id="h-uselect" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        USelect
      </h2>
      <div class="grid max-w-2xl gap-4">
        <USelect v-model="selectValue" :options="selectOptions" label="Vault" />
        <USelect v-for="size in inputSizes" :key="size" v-model="selectValue" :options="selectOptions" :size="size" :placeholder="`Size ${size}`" />
        <USelect v-model="selectValue" :options="selectOptions" label="Vault" help-text="Pick the vault to manage" />
        <USelect v-model="selectValue" :options="selectOptions" label="Vault" error="This vault is not available" />
        <USelect v-model="selectValue" :options="selectOptions" label="Vault" required />
        <USelect v-model="selectValue" :options="selectOptions" label="Vault" disabled />
      </div>
    </section>

    <!-- ============ USlider ============ -->
    <section class="mt-10" aria-labelledby="h-uslider">
      <h2 id="h-uslider" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        USlider
      </h2>
      <div class="grid max-w-2xl gap-6">
        <div v-for="accent in sliderAccents" :key="accent" class="flex items-center gap-4">
          <span class="w-24 text-sm text-theme-primary/70">{{ accent }}</span>
          <USlider v-model="sliderValue" :accent="accent" :aria-label="`Slider ${accent}`" />
        </div>
        <div class="flex items-center gap-4">
          <span class="w-24 text-sm text-theme-primary/70">Values</span>
          <USlider :model-value="25" aria-label="Slider 25" />
          <USlider :model-value="50" aria-label="Slider 50" />
          <USlider :model-value="75" aria-label="Slider 75" />
        </div>
        <div class="flex items-center gap-4">
          <span class="w-24 text-sm text-theme-primary/70">Disabled</span>
          <USlider v-model="sliderValue" disabled aria-label="Slider disabled" />
        </div>
      </div>
    </section>

    <!-- ============ UProgressBar ============ -->
    <section class="mt-10" aria-labelledby="h-uprogressbar">
      <h2 id="h-uprogressbar" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        UProgressBar
      </h2>
      <div class="grid max-w-2xl gap-4">
        <div class="flex items-center gap-4">
          <span class="w-24 text-sm text-theme-primary/70">Values</span>
          <UProgressBar :model-value="0" :ariaLabel="'Progress 0'" />
          <UProgressBar :model-value="25" :ariaLabel="'Progress 25'" />
          <UProgressBar :model-value="50" :ariaLabel="'Progress 50'" />
          <UProgressBar :model-value="75" :ariaLabel="'Progress 75'" />
          <UProgressBar :model-value="100" :ariaLabel="'Progress 100'" />
        </div>
        <div class="flex items-center gap-4">
          <span class="w-24 text-sm text-theme-primary/70">Radiation</span>
          <UProgressBar :model-value="80" :radiation="20" :ariaLabel="'Progress with radiation'" />
        </div>
        <div class="flex items-center gap-4">
          <span class="w-24 text-sm text-theme-primary/70">Heights</span>
          <UProgressBar :model-value="60" :height="6" :ariaLabel="'Progress height 6'" />
          <UProgressBar :model-value="60" :height="10" :ariaLabel="'Progress height 10'" />
          <UProgressBar :model-value="60" :height="16" :ariaLabel="'Progress height 16'" />
        </div>
        <div class="flex items-center gap-4">
          <span class="w-24 text-sm text-theme-primary/70">No glow</span>
          <UProgressBar :model-value="60" :glow="false" :ariaLabel="'Progress no glow'" />
        </div>
        <div class="flex items-center gap-4">
          <span class="w-24 text-sm text-theme-primary/70">Animations</span>
          <UProgressBar :model-value="60" animation="pulse" :ariaLabel="'Progress pulse'" />
          <UProgressBar :model-value="60" animation="shimmer" :ariaLabel="'Progress shimmer'" />
          <UProgressBar :model-value="60" animation="shine" :ariaLabel="'Progress shine'" />
        </div>
        <div class="flex items-center gap-4">
          <span class="w-24 text-sm text-theme-primary/70">Color</span>
          <UProgressBar :model-value="60" color="#facc15" :ariaLabel="'Progress custom color'" />
        </div>
      </div>
    </section>

    <!-- ============ USkeleton ============ -->
    <section class="mt-10" aria-labelledby="h-uskeleton">
      <h2 id="h-uskeleton" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        USkeleton
      </h2>
      <div class="flex flex-wrap items-center gap-3">
        <USkeleton v-for="rounded in skeletonRounded" :key="rounded" :rounded="rounded" width="8rem" height="2rem" />
      </div>
      <div class="mt-4 flex flex-wrap items-center gap-3">
        <USkeleton width="4rem" height="1rem" />
        <USkeleton width="8rem" height="1.5rem" />
        <USkeleton width="12rem" height="2rem" />
        <USkeleton width="6rem" height="6rem" rounded="full" />
      </div>
      <div class="mt-4 flex flex-wrap items-center gap-3">
        <USkeleton width="8rem" height="2rem" :animate="false" />
      </div>
    </section>

    <!-- ============ UTooltip ============ -->
    <section class="mt-10" aria-labelledby="h-utooltip">
      <h2 id="h-utooltip" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        UTooltip
      </h2>
      <p class="mb-4 text-sm text-theme-primary/60">
        The spec focuses the “Tooltip top” trigger so the teleported tooltip is visible for capture.
      </p>
      <div class="flex flex-wrap items-center gap-3">
        <UTooltip text="Tooltip on top" position="top" :delay="0">
          <UButton>Tooltip top</UButton>
        </UTooltip>
        <UTooltip text="Tooltip on bottom" position="bottom" :delay="0">
          <UButton>Tooltip bottom</UButton>
        </UTooltip>
        <UTooltip text="Tooltip on left" position="left" :delay="0">
          <UButton>Tooltip left</UButton>
        </UTooltip>
        <UTooltip text="Tooltip on right" position="right" :delay="0">
          <UButton>Tooltip right</UButton>
        </UTooltip>
      </div>
    </section>

    <!-- ============ UIconButton ============ -->
    <section class="mt-10" aria-labelledby="h-uiconbutton">
      <h2 id="h-uiconbutton" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        UIconButton
      </h2>
      <div class="flex flex-wrap items-center gap-3">
        <UIconButton icon="mdi:check" label="Confirm" />
        <UIconButton icon="mdi:close" label="Cancel" />
        <UIconButton icon="mdi:delete" label="Delete" variant="danger" />
        <UIconButton icon="mdi:wrench" label="Repair" disabled />
      </div>
    </section>

    <!-- ============ UToast ============ -->
    <section class="mt-10" aria-labelledby="h-utoast">
      <h2 id="h-utoast" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        UToast
      </h2>
      <p class="mb-4 text-sm text-theme-primary/60">
        Inline fixtures; the global UToastContainer is populated on mount (top-right of the viewport).
      </p>
      <div class="grid max-w-2xl gap-3">
        <UToast v-for="toast in toastFixtures" :key="toast.id" :toast="toast" />
      </div>
    </section>

    <!-- ============ UToastContainer ============ -->
    <section class="mt-10" aria-labelledby="h-utoastcontainer">
      <h2 id="h-utoastcontainer" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        UToastContainer
      </h2>
      <p class="text-sm text-theme-primary/60">
        Mounted globally in App.vue; seeded with four duration-0 toasts on mount (visible top-right).
      </p>
    </section>

    <!-- ============ SettingItem ============ -->
    <section class="mt-10" aria-labelledby="h-settingitem">
      <h2 id="h-settingitem" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        SettingItem
      </h2>
      <div class="max-w-md rounded-lg border-2 border-theme-primary/20 bg-surface">
        <SettingItem label="Vault name" value="Vault 101" />
        <SettingItem label="Population" :value="42" />
        <SettingItem label="Happiness" :value="87.5" :decimals="1" unit="%" />
        <SettingItem label="Radiation mode" :value="true" />
        <SettingItem label="Auto-collect" :value="false" />
      </div>
    </section>
  </div>
</template>
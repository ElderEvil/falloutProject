<script setup lang="ts">
/**
 * UiCatalogView — dev-only regression catalog for the shadcn-vue primitives.
 *
 * Renders every component from `@/core/components/ui` in all variants, sizes
 * and relevant states so a Playwright aria snapshot + pixel screenshot can
 * prove a primitive change is visually neutral.
 *
 * Overlay primitives are rendered open/visible (never hover-dependent):
 * - Dialog is open by default.
 * - Tooltip triggers are focused by the spec (focus, not hover).
 * - Toast fixtures are rendered inline; the global Toaster (mounted
 *   in App.vue) is populated on mount with duration-0 toasts.
 */
import { onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { Alert, AlertDescription, AlertTitle } from '@/core/components/ui/alert'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/core/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/core/components/ui/dialog'
import { Input } from '@/core/components/ui/input'
import { Label } from '@/core/components/ui/label'
import { Progress } from '@/core/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/core/components/ui/select'
import { Skeleton } from '@/core/components/ui/skeleton'
import { Slider } from '@/core/components/ui/slider'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/core/components/ui/tabs'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/core/components/ui/tooltip'
import { Toast, Toaster } from '@/core/components/ui/toast'
import HealthRadiationBar from '@/core/components/common/HealthRadiationBar.vue'
import SettingItem from '@/core/components/ui/SettingItem.vue'
import { useToast, type Toast as ToastModel } from '@/core/composables/useToast'

// --- toast seeding: populate the global Toaster deterministically ---
const { toasts, remove, show } = useToast()
onMounted(() => {
  while (toasts.value.length > 0) remove(toasts.value[0]!.id)
  show('Vault saved successfully', 'success', 0)
  show('Radiation levels critical', 'error', 0)
  show('New dweller arrived', 'warning', 0)
  show('Quest completed', 'info', 0)
})

const toastFixtures: ToastModel[] = [
  { id: 'toast-fixture-success', message: 'Direct Toast — success', variant: 'success' },
  { id: 'toast-fixture-error', message: 'Direct Toast — error', variant: 'error' },
  { id: 'toast-fixture-warning', message: 'Direct Toast — warning', variant: 'warning', count: 3 },
  { id: 'toast-fixture-info', message: 'Direct Toast — info', variant: 'info' },
]

const buttonVariants = ['default', 'outline', 'secondary', 'ghost', 'destructive', 'link'] as const
const buttonSizes = ['default', 'xs', 'sm', 'lg'] as const
const iconButtonSizes = ['icon-xs', 'icon-sm', 'icon', 'icon-lg'] as const
const badgeVariants = ['default', 'secondary', 'destructive', 'outline', 'ghost', 'link'] as const
const selectOptions = [
  { value: 'vault-1', label: 'Vault 101' },
  { value: 'vault-2', label: 'Vault 13' },
  { value: 'vault-3', label: 'Vault 111' },
]

const modalOpen = ref(true)
const activeTab = ref('overview')
const selectValue = ref<string>('vault-1')
const sliderValue = ref(50)
const inputValue = ref('')

const setActiveTab = (value: unknown) => {
  activeTab.value = String(value)
}
const setSelectValue = (value: unknown) => {
  selectValue.value = value == null ? '' : String(value)
}
const setSlider = (value: number[] | undefined) => {
  sliderValue.value = value?.[0] ?? 0
}
</script>

<template>
  <div class="mx-auto max-w-6xl px-6 py-8">
    <h1 class="text-3xl font-bold terminal-glow text-theme-primary">UI Catalog</h1>
    <p class="mt-2 text-sm text-theme-primary/60">
      Dev-only regression catalog for the shadcn-vue primitives in
      <code class="text-theme-primary">@/core/components/ui</code>, captured by the Playwright visual net.
    </p>

    <!-- ============ Button ============ -->
    <section class="mt-10" aria-labelledby="h-button">
      <h2 id="h-button" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        Button
      </h2>
      <div class="flex flex-wrap items-center gap-3">
        <Button v-for="variant in buttonVariants" :key="variant" :variant="variant">
          {{ variant }}
        </Button>
      </div>
      <div class="mt-4 flex flex-wrap items-center gap-3">
        <Button v-for="size in buttonSizes" :key="size" :size="size">Size {{ size }}</Button>
      </div>
      <div class="mt-4 flex flex-wrap items-center gap-3">
        <Button disabled>Disabled</Button>
        <Button :disabled="true">
          <Icon icon="mdi:loading" class="animate-spin" />
          Loading
        </Button>
        <Button>
          <Icon icon="mdi:check" />
          With icon
        </Button>
        <Button>
          Icon right
          <Icon icon="mdi:wrench" />
        </Button>
        <Button class="w-48">Block</Button>
      </div>
    </section>

    <!-- ============ Input ============ -->
    <section class="mt-10" aria-labelledby="h-input">
      <h2 id="h-input" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        Input
      </h2>
      <div class="grid max-w-2xl gap-4">
        <Input v-model="inputValue" placeholder="Default input" />
        <div class="flex flex-col gap-1">
          <Label for="catalog-input-label">Dweller name</Label>
          <Input id="catalog-input-label" v-model="inputValue" placeholder="e.g. Butch" required />
        </div>
        <Input v-model="inputValue" placeholder="Disabled input" disabled />
        <Input v-model="inputValue" type="password" placeholder="Password" />
      </div>
    </section>

    <!-- ============ Badge ============ -->
    <section class="mt-10" aria-labelledby="h-badge">
      <h2 id="h-badge" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        Badge
      </h2>
      <div class="flex flex-wrap items-center gap-3">
        <Badge v-for="variant in badgeVariants" :key="variant" :variant="variant">{{ variant }}</Badge>
      </div>
      <div class="mt-4 flex flex-wrap items-center gap-3">
        <Badge variant="default">
          <Icon icon="mdi:alert" />
          With icon
        </Badge>
        <Badge variant="outline">
          <Icon icon="mdi:information" />
          With icon
        </Badge>
      </div>
    </section>

    <!-- ============ Card ============ -->
    <section class="mt-10" aria-labelledby="h-card">
      <h2 id="h-card" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        Card
      </h2>
      <div class="grid gap-4 md:grid-cols-3">
        <Card>
          <CardContent>
            <p class="text-sm text-theme-primary/80">Default card</p>
          </CardContent>
        </Card>
        <Card class="gap-0 rounded-lg border-2 border-theme-primary/20 p-6 shadow-glow-md ring-0">
          <p class="text-sm text-theme-primary/80">Glow enabled</p>
        </Card>
        <Card class="gap-0 rounded-lg border-2 border-theme-primary/20 p-6 ring-0 crt-screen">
          <p class="text-sm text-theme-primary/80">CRT screen effect</p>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Slotted card</CardTitle>
          </CardHeader>
          <CardContent>
            <p class="text-sm text-theme-primary/80">Header + footer composition</p>
          </CardContent>
          <CardFooter>
            <Button size="sm">Footer action</Button>
          </CardFooter>
        </Card>
      </div>
    </section>

    <!-- ============ Alert ============ -->
    <section class="mt-10" aria-labelledby="h-alert">
      <h2 id="h-alert" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        Alert
      </h2>
      <div class="grid max-w-2xl gap-3">
        <Alert variant="default">
          <AlertTitle>Success</AlertTitle>
          <AlertDescription>Vault created successfully</AlertDescription>
        </Alert>
        <Alert variant="destructive">
          <AlertTitle>Danger</AlertTitle>
          <AlertDescription>Radiation leak detected</AlertDescription>
        </Alert>
      </div>
    </section>

    <!-- ============ Dialog ============ -->
    <section class="mt-10" aria-labelledby="h-dialog">
      <h2 id="h-dialog" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        Dialog
      </h2>
      <p class="text-sm text-theme-primary/60">
        Rendered open (header, body and footer) so capture is deterministic.
      </p>
      <Dialog v-model:open="modalOpen" :modal="false">
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm evacuation</DialogTitle>
          </DialogHeader>
          <p class="text-sm text-theme-primary/80">
            Are you sure you want to evacuate this vault? All dwellers will be relocated.
          </p>
          <DialogFooter>
            <Button variant="secondary">Cancel</Button>
            <Button variant="destructive">Evacuate</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>

    <!-- ============ Tabs ============ -->
    <section class="mt-10" aria-labelledby="h-tabs">
      <h2 id="h-tabs" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        Tabs
      </h2>
      <Tabs :model-value="activeTab" @update:model-value="setActiveTab">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="dwellers">Dwellers</TabsTrigger>
          <TabsTrigger value="storage">Storage</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          <p class="text-sm text-theme-primary/80">Overview panel</p>
        </TabsContent>
        <TabsContent value="dwellers">
          <p class="text-sm text-theme-primary/80">Dwellers panel</p>
        </TabsContent>
        <TabsContent value="storage">
          <p class="text-sm text-theme-primary/80">Storage panel</p>
        </TabsContent>
      </Tabs>
    </section>

    <!-- ============ Select ============ -->
    <section class="mt-10" aria-labelledby="h-select">
      <h2 id="h-select" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        Select
      </h2>
      <div class="grid max-w-2xl gap-4">
        <div class="flex flex-col gap-1">
          <Label for="catalog-select">Vault</Label>
          <Select :model-value="selectValue" @update:model-value="setSelectValue">
            <SelectTrigger id="catalog-select" class="w-full">
              <SelectValue placeholder="Pick a vault" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="option in selectOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Select :model-value="selectValue" @update:model-value="setSelectValue">
          <SelectTrigger size="sm" class="w-full" aria-label="Compact vault select">
            <SelectValue placeholder="Size sm" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="option in selectOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
    </section>

    <!-- ============ Slider ============ -->
    <section class="mt-10" aria-labelledby="h-slider">
      <h2 id="h-slider" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        Slider
      </h2>
      <div class="grid max-w-2xl gap-6">
        <div class="flex items-center gap-4">
          <span class="w-24 text-sm text-theme-primary/70">Value</span>
          <Slider :model-value="[sliderValue]" aria-label="Slider value" @update:model-value="setSlider" />
        </div>
        <div class="flex items-center gap-4">
          <span class="w-24 text-sm text-theme-primary/70">Fixed</span>
          <Slider :model-value="[25]" aria-label="Slider 25" />
          <Slider :model-value="[50]" aria-label="Slider 50" />
          <Slider :model-value="[75]" aria-label="Slider 75" />
        </div>
        <div class="flex items-center gap-4">
          <span class="w-24 text-sm text-theme-primary/70">Disabled</span>
          <Slider :model-value="[sliderValue]" disabled aria-label="Slider disabled" />
        </div>
      </div>
    </section>

    <!-- ============ Progress ============ -->
    <section class="mt-10" aria-labelledby="h-progress">
      <h2 id="h-progress" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        Progress
      </h2>
      <div class="grid max-w-2xl gap-4">
        <div class="flex items-center gap-4">
          <span class="w-24 text-sm text-theme-primary/70">Values</span>
          <!-- @vue-ignore -->
          <Progress :model-value="0" aria-label="Progress 0" />
          <!-- @vue-ignore -->
          <Progress :model-value="25" aria-label="Progress 25" />
          <!-- @vue-ignore -->
          <Progress :model-value="50" aria-label="Progress 50" />
          <!-- @vue-ignore -->
          <Progress :model-value="75" aria-label="Progress 75" />
          <!-- @vue-ignore -->
          <Progress :model-value="100" aria-label="Progress 100" />
        </div>
        <div class="flex items-center gap-4">
          <span class="w-24 text-sm text-theme-primary/70">Heights</span>
          <Progress :model-value="60" class="h-1" />
          <Progress :model-value="60" class="h-2.5" />
          <Progress :model-value="60" class="h-4" />
        </div>
        <div class="flex items-center gap-4">
          <span class="w-24 text-sm text-theme-primary/70">Custom color</span>
          <Progress
            :model-value="60"
            class="catalog-progress bar-fill"
            :style="{ '--bar-fill': '#facc15' }"
          />
        </div>
        <div class="flex items-center gap-4">
          <span class="w-24 text-sm text-theme-primary/70">Radiation</span>
          <HealthRadiationBar :value="80" :radiation="20" aria-label="Health with radiation" />
        </div>
      </div>
    </section>

    <!-- ============ Skeleton ============ -->
    <section class="mt-10" aria-labelledby="h-skeleton">
      <h2 id="h-skeleton" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        Skeleton
      </h2>
      <div class="flex flex-wrap items-center gap-3">
        <Skeleton class="h-8 w-32 rounded-none" />
        <Skeleton class="h-8 w-32 rounded-sm" />
        <Skeleton class="h-8 w-32 rounded-md" />
        <Skeleton class="h-8 w-32 rounded-lg" />
        <Skeleton class="h-24 w-24 rounded-full" />
      </div>
    </section>

    <!-- ============ Tooltip ============ -->
    <section class="mt-10" aria-labelledby="h-tooltip">
      <h2 id="h-tooltip" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        Tooltip
      </h2>
      <p class="mb-4 text-sm text-theme-primary/60">
        The spec focuses the “Tooltip top” trigger so the teleported tooltip is visible for capture.
      </p>
      <TooltipProvider :delay-duration="200">
        <div class="flex flex-wrap items-center gap-3">
          <Tooltip :default-open="true">
            <TooltipTrigger as-child>
              <button type="button" class="rounded border border-theme-primary px-3 py-1.5 text-sm text-theme-primary">
                Tooltip top
              </button>
            </TooltipTrigger>
            <TooltipContent side="top">Tooltip on top</TooltipContent>
          </Tooltip>
          <Tooltip :default-open="true">
            <TooltipTrigger as-child>
              <button type="button" class="rounded border border-theme-primary px-3 py-1.5 text-sm text-theme-primary">
                Tooltip bottom
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom">Tooltip on bottom</TooltipContent>
          </Tooltip>
          <Tooltip :default-open="true">
            <TooltipTrigger as-child>
              <button type="button" class="rounded border border-theme-primary px-3 py-1.5 text-sm text-theme-primary">
                Tooltip left
              </button>
            </TooltipTrigger>
            <TooltipContent side="left">Tooltip on left</TooltipContent>
          </Tooltip>
          <Tooltip :default-open="true">
            <TooltipTrigger as-child>
              <button type="button" class="rounded border border-theme-primary px-3 py-1.5 text-sm text-theme-primary">
                Tooltip right
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">Tooltip on right</TooltipContent>
          </Tooltip>
        </div>
      </TooltipProvider>
    </section>

    <!-- ============ Icon Button ============ -->
    <section class="mt-10" aria-labelledby="h-iconbutton">
      <h2 id="h-iconbutton" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        Icon Button
      </h2>
      <div class="flex flex-wrap items-center gap-3">
        <Button v-for="size in iconButtonSizes" :key="size" :size="size" variant="ghost" :aria-label="`Icon ${size}`">
          <Icon icon="mdi:wrench" />
        </Button>
        <Button size="icon-sm" variant="ghost" aria-label="Delete" disabled>
          <Icon icon="mdi:delete" class="text-danger" />
        </Button>
      </div>
    </section>

    <!-- ============ Toast ============ -->
    <section class="mt-10" aria-labelledby="h-toast">
      <h2 id="h-toast" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        Toast
      </h2>
      <p class="mb-4 text-sm text-theme-primary/60">
        Inline fixtures; the global Toaster is populated on mount (top-right of the viewport).
      </p>
      <div class="grid max-w-2xl gap-3">
        <Toast v-for="toast in toastFixtures" :key="toast.id" :toast="toast" />
      </div>
    </section>

    <!-- ============ Toaster ============ -->
    <section class="mt-10" aria-labelledby="h-toaster">
      <h2 id="h-toaster" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold text-theme-primary">
        Toaster
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

<style scoped>
.catalog-progress :deep([data-slot='progress-indicator']) {
  background: var(--bar-fill);
}
</style>

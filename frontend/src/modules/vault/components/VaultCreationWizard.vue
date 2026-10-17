<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Alert, AlertDescription } from '@/core/components/ui/alert'
import { Button } from '@/core/components/ui/button'
import { Label } from '@/core/components/ui/label'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/core/components/ui/card'
import { ToggleGroup, ToggleGroupItem } from '@/core/components/ui/toggle-group'
import VaultNumberField from './VaultNumberField.vue'
import { parseVaultNumber, type VaultNumberData } from '../schemas/vault'

const props = defineProps<{ creating: boolean }>()
const emit = defineEmits<{ create: [options: VaultNumberData] }>()
const steps = ['Vault number', 'Setup', 'Review']
const step = ref(0)
const number = ref('')
const vaultMode = ref<VaultNumberData['vaultMode']>('standard')
const boosted = ref(false)
const numberField = ref<InstanceType<typeof VaultNumberField> | null>(null)
const heading = ref<HTMLElement | null>(null)
const isSurvival = computed(() => vaultMode.value === 'survival')
const modes = [
  {
    value: 'standard',
    label: 'Standard',
    description: 'Dwellers can be revived with caps. A little breathing room for a new Overseer.',
  },
  {
    value: 'survival',
    label: 'Survival',
    description: 'Deaths are permanent. The wasteland offers no second chances.',
  },
] as const

function selectMode(value: unknown) {
  if (value !== 'standard' && value !== 'survival') return
  vaultMode.value = value
  if (value === 'survival') boosted.value = false
}

async function focusStep() {
  await nextTick()
  if (step.value === 0) numberField.value?.focus()
  else heading.value?.focus({ preventScroll: true })
}
onMounted(focusStep)
watch(step, focusStep)

function advance() {
  if (props.creating) return
  if (step.value === 0 && !numberField.value?.isValid()) return
  if (step.value < steps.length - 1) {
    step.value++
    return
  }
  emit('create', {
    number: parseVaultNumber(number.value),
    boosted: boosted.value,
    vaultMode: vaultMode.value,
  })
}
</script>

<template>
  <Card
    class="w-full max-w-lg gap-0 overflow-hidden border-theme-primary/30 bg-surface shadow-glow-sm"
  >
    <CardHeader class="gap-4 border-b border-theme-primary/20 pb-5">
      <div class="flex items-center justify-between gap-3 text-xs text-theme-primary/65">
        <span class="tracking-widest">VAULT-TEC // COMMISSIONING</span>
        <span class="shrink-0">{{ step + 1 }} / {{ steps.length }}</span>
      </div>
      <div class="flex items-center justify-between gap-3">
        <div class="flex flex-col gap-2">
          <CardTitle class="text-2xl terminal-glow"><h2>Create New Vault</h2></CardTitle>
          <p class="text-xs leading-5 text-theme-primary/65">
            Building a brighter future. Underground.
          </p>
        </div>
        <svg
          viewBox="0 0 80 48"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
          class="h-8 w-12 shrink-0 text-theme-primary/55"
        >
          <path d="M2 16h17M6 24h12M10 32h9M61 16h17M62 24h12M61 32h9" />
          <path d="M32 5h16l3 6 7 3v20l-7 3-3 6H32l-3-6-7-3V14l7-3z" />
          <circle cx="40" cy="24" r="12" />
          <path d="M35 19l5 12 5-12M37 25h6" />
        </svg>
      </div>
      <ol aria-label="Vault setup progress" class="grid grid-cols-3 gap-2">
        <li
          v-for="(label, index) in steps"
          :key="label"
          :aria-current="index === step ? 'step' : undefined"
        >
          <Button
            type="button"
            variant="ghost"
            size="sm"
            class="h-auto w-full flex-col gap-1 whitespace-normal rounded-none border-b-2 px-1 py-2 text-xs"
            :class="
              index === step
                ? 'border-theme-primary text-theme-primary'
                : 'border-theme-primary/20 text-theme-primary/60'
            "
            :disabled="index > step || creating"
            @click="step = index"
          >
            <span aria-hidden="true" class="text-[0.65rem]">0{{ index + 1 }}</span>
            {{ label }}
          </Button>
        </li>
      </ol>
    </CardHeader>

    <form novalidate :aria-busy="creating" @submit.prevent="advance">
      <CardContent class="flex flex-col gap-5 pt-6 pb-6">
        <div>
          <h3 ref="heading" tabindex="-1" class="text-lg font-bold text-theme-primary outline-none">
            {{
              ['Choose your vault number', 'Choose how you start', 'Ready to open the doors?'][step]
            }}
          </h3>
          <p v-if="step === 0" class="mt-2 text-sm leading-6 text-theme-primary/65">
            Choose an unused vault number (1-999). Your little corner of a very big wasteland.
          </p>
          <p v-else-if="step === 1" class="mt-2 text-sm leading-6 text-theme-primary/65">
            Set the stakes, then choose your starting point.
          </p>
          <p v-else class="mt-2 text-sm leading-6 text-theme-primary/65">
            Your vault. Your rules. Vault-Tec supplies the paperwork. Check your choices below.
          </p>
        </div>

        <VaultNumberField
          v-if="step === 0"
          ref="numberField"
          :model-value="number"
          @update:model-value="number = String($event)"
        />

        <template v-else-if="step === 1">
          <fieldset :disabled="creating" class="flex flex-col gap-3">
            <legend class="mb-3 text-xs font-bold tracking-widest text-theme-primary/70">
              VAULT MODE
            </legend>
            <ToggleGroup
              type="single"
              :model-value="vaultMode"
              :spacing="8"
              class="grid w-full grid-cols-1 gap-2"
              @update:model-value="selectMode"
            >
              <ToggleGroupItem
                v-for="mode in modes"
                :key="mode.value"
                :value="mode.value"
                class="h-auto w-full min-w-0 items-start gap-3 whitespace-normal rounded border border-theme-primary/20 p-4 text-left data-[state=on]:border-theme-primary data-[state=on]:bg-theme-primary/10"
              >
                <Icon
                  :icon="
                    mode.value === 'standard' ? 'mdi:shield-check-outline' : 'mdi:skull-outline'
                  "
                  class="mt-0.5 shrink-0"
                />
                <span class="flex min-w-0 flex-col gap-1">
                  <span class="font-semibold">{{ mode.label }}</span>
                  <span class="text-xs leading-5 text-theme-primary/65">{{
                    mode.description
                  }}</span>
                </span>
              </ToggleGroupItem>
            </ToggleGroup>
            <p class="flex items-start gap-2 text-xs leading-5 text-warning">
              <Icon icon="mdi:lock-outline" class="mt-0.5 shrink-0" />
              Vault mode cannot be changed later.
            </p>
          </fieldset>

          <fieldset class="border-t border-theme-primary/20 pt-4">
            <legend class="sr-only">Starting point</legend>
            <Label for="boosted-start" class="flex items-start gap-3 text-sm">
              <input
                id="boosted-start"
                v-model="boosted"
                type="checkbox"
                :disabled="isSurvival || creating"
                class="mt-1 size-4 shrink-0 accent-theme-primary scheme-dark"
              />
              <span class="flex flex-col gap-1">
                <span class="font-semibold"
                  >Boosted Start
                  <span class="font-normal text-theme-primary/50">/ optional</span></span
                >
                <span class="text-xs leading-5 text-theme-primary/65"
                  >Skip ahead with an expanded vault and extra supplies.</span
                >
                <span v-if="isSurvival" class="text-xs text-warning"
                  >Not available in Survival mode.</span
                >
                <span v-else class="text-xs leading-5 text-theme-primary/65"
                  >Leave off to build from scratch and learn as you grow.</span
                >
              </span>
            </Label>
            <details class="mt-3 text-xs leading-5 text-theme-primary/65">
              <summary class="cursor-pointer text-theme-primary/80">
                What's included in Boosted Start?
              </summary>
              <p class="mt-2">
                Creates an expanded vault with medical, science, crafting, an arena, and all seven
                training rooms with sessions underway—plus extra objectives and caps for upgrades.
              </p>
            </details>
          </fieldset>
        </template>

        <template v-else>
          <dl
            class="flex flex-col divide-y divide-theme-primary/20 rounded border border-theme-primary/20 bg-surface-sunken px-4"
          >
            <div class="flex items-center justify-between gap-4 py-4">
              <dt class="text-sm text-theme-primary/65">Vault number</dt>
              <dd class="text-2xl font-bold terminal-glow">
                {{ parseVaultNumber(number).toString().padStart(3, '0') }}
              </dd>
            </div>
            <div class="flex items-center justify-between gap-4 py-4">
              <dt class="text-sm text-theme-primary/65">Vault mode</dt>
              <dd class="font-semibold">{{ isSurvival ? 'Survival' : 'Standard' }}</dd>
            </div>
            <div class="flex items-center justify-between gap-4 py-4">
              <dt class="text-sm text-theme-primary/65">Starting point</dt>
              <dd class="font-semibold">{{ boosted ? 'Boosted Start' : 'Build from scratch' }}</dd>
            </div>
          </dl>
          <p v-if="isSurvival" class="text-sm leading-6 text-warning">
            Deaths are permanent in this vault. Mode cannot be changed later.
          </p>
          <Alert class="border-warning/40 bg-warning/10 text-warning">
            <AlertDescription class="text-warning"
              >Vaults are experimental. Vault data might be deleted in a future
              update.</AlertDescription
            >
          </Alert>
        </template>
      </CardContent>
      <CardFooter class="justify-between gap-3 border-t border-theme-primary/20 pt-4 pb-4">
        <Button v-if="step > 0" type="button" variant="ghost" :disabled="creating" @click="step--"
          >Back</Button
        >
        <Button
          type="submit"
          :disabled="creating || (step === 0 && !number)"
          class="ml-auto shadow-glow-sm"
        >
          <Icon
            v-if="creating"
            icon="mdi:loading"
            class="animate-spin motion-reduce:animate-none"
          />
          {{ creating ? 'Creating...' : step === steps.length - 1 ? 'Create Vault' : 'Continue' }}
        </Button>
      </CardFooter>
    </form>
  </Card>
</template>

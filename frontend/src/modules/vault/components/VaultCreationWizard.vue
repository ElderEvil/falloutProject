<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Alert, AlertDescription } from '@/core/components/ui/alert'
import { Button } from '@/core/components/ui/button'
import { Label } from '@/core/components/ui/label'
import { Switch } from '@/core/components/ui/switch'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/core/components/ui/card'
import { ToggleGroup, ToggleGroupItem } from '@/core/components/ui/toggle-group'
import VaultNumberField from './VaultNumberField.vue'
import { parseVaultNumber, type VaultNumberData } from '../schemas/vault'
import type { VaultScenarioOption } from '../stores/vault'
import { useVisualEffects } from '@/core/composables/useVisualEffects'

const props = withDefaults(
  defineProps<{ creating: boolean; scenarios?: VaultScenarioOption[] }>(),
  { scenarios: () => [] }
)
const emit = defineEmits<{ create: [options: VaultNumberData] }>()
const { glowClass } = useVisualEffects()
const steps = ['Vault number', 'Setup', 'Review']
const step = ref(0)
const number = ref('')
const vaultMode = ref<VaultNumberData['vaultMode']>('standard')
const ordinaryBoosted = ref(false)
const selectedScenarioKey = ref<string>()
const matchingScenario = computed(
  () => props.scenarios.find((scenario) => scenario.number === Number(number.value)) ?? null
)
const experiments = computed(() => props.scenarios.filter((scenario) => !scenario.expedition))
const selectedScenario = computed(() =>
  matchingScenario.value?.key === selectedScenarioKey.value ? matchingScenario.value : null
)
const numberField = ref<InstanceType<typeof VaultNumberField> | null>(null)
const heading = ref<HTMLElement | null>(null)
const isSurvival = computed(() => vaultMode.value === 'survival')
const boosted = computed(
  () => !isSurvival.value && (selectedScenario.value?.default_boosted ?? ordinaryBoosted.value)
)

function updateNumber(value: string) {
  number.value = String(value)
  if (!selectedScenario.value) selectedScenarioKey.value = undefined
}

function chooseExperiment(scenario: VaultScenarioOption) {
  number.value = String(scenario.number)
  selectedScenarioKey.value = scenario.key
  step.value = 1
}

const modes = [
  {
    value: 'standard',
    label: 'Standard',
    icon: 'mdi:shield-check-outline',
    description: 'Recommended for your first vault. Fallen dwellers can be revived with caps.',
  },
  {
    value: 'survival',
    label: 'Survival',
    icon: 'mdi:skull-outline',
    description: 'Deaths are permanent. Every staffing and expedition decision carries more risk.',
  },
] as const

const summary = computed(() => {
  const rows = [
    ['Vault number', parseVaultNumber(number.value).toString().padStart(3, '0')],
    ['Vault mode', isSurvival.value ? 'Survival' : 'Standard'],
  ]
  if (selectedScenario.value) rows.push(['Scenario', selectedScenario.value.title])
  else rows.push(['Starting point', boosted.value ? 'Boosted Start' : 'Build from scratch'])
  return rows
})

function selectMode(value: unknown) {
  if (value !== 'standard' && value !== 'survival') return
  vaultMode.value = value
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
  const payload: VaultNumberData = {
    number: parseVaultNumber(number.value),
    boosted: boosted.value,
    vaultMode: vaultMode.value,
  }
  if (selectedScenario.value) payload.scenario = selectedScenario.value.key
  emit('create', payload)
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
          <CardTitle class="text-2xl" :class="glowClass"><h2>Create New Vault</h2></CardTitle>
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
              ['Choose your vault number', 'Choose your vault mode', 'Ready to open the doors?'][
                step
              ]
            }}
          </h3>
          <p v-if="step === 0" class="mt-2 text-sm leading-6 text-theme-primary/65">
            Enter a vault number from 1 to 999{{
              experiments.length ? ', or choose an experiment below.' : '.'
            }}
          </p>
          <p v-else-if="step === 1" class="mt-2 text-sm leading-6 text-theme-primary/65">
            Choose whether dwellers can be revived.
          </p>
          <p v-else class="mt-2 text-sm leading-6 text-theme-primary/65">
            Check your vault details before you begin.
          </p>
        </div>

        <template v-if="step === 0">
          <VaultNumberField
            ref="numberField"
            :model-value="number"
            @update:model-value="updateNumber"
          />

          <fieldset v-if="experiments.length" class="border-t border-theme-primary/20 pt-4">
            <legend class="pr-2 text-xs font-bold tracking-widest text-theme-primary/70">
              EXPERIMENTAL STARTS
            </legend>
            <div class="grid gap-2">
              <Button
                v-for="scenario in experiments"
                :key="scenario.key"
                type="button"
                variant="outline"
                class="h-auto justify-start whitespace-normal p-3 text-left"
                @click="chooseExperiment(scenario)"
              >
                <Icon icon="mdi:flask-outline" class="shrink-0" :ariaHidden="true" />
                <span>{{ scenario.title }}</span>
              </Button>
            </div>
          </fieldset>
        </template>

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
                <Icon :icon="mode.icon" class="mt-0.5 shrink-0" />
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

          <fieldset v-if="matchingScenario" class="border-t border-theme-primary/20 pt-4">
            <legend class="sr-only">Scenario start</legend>
            <Label for="scenario-start" class="flex items-start gap-3 text-sm">
              <Switch
                id="scenario-start"
                :checked="Boolean(selectedScenario)"
                :disabled="creating"
                @update:checked="selectedScenarioKey = $event ? matchingScenario.key : undefined"
                class="mt-1"
              />
              <span class="flex flex-col gap-1">
                <span class="font-semibold"
                  >{{ matchingScenario.title }}
                  <span class="font-normal text-theme-primary/50">/ optional</span></span
                >
                <span class="text-xs leading-5 text-theme-primary/65">{{
                  matchingScenario.description
                }}</span>
                <span
                  v-if="matchingScenario.expedition"
                  class="text-xs leading-5 text-theme-primary/65"
                  >Multi-room encounters are disabled for scenario starts.</span
                >
              </span>
            </Label>
          </fieldset>

          <fieldset v-if="!selectedScenario" class="border-t border-theme-primary/20 pt-4">
            <legend class="sr-only">Starting point</legend>
            <Label for="boosted-start" class="flex items-start gap-3 text-sm">
              <Switch
                id="boosted-start"
                :checked="boosted"
                :disabled="creating || isSurvival"
                class="mt-1"
                @update:checked="ordinaryBoosted = $event"
              />
              <span class="flex flex-col gap-1">
                <span class="font-semibold">Boosted Start</span>
                <span class="text-xs leading-5 text-theme-primary/65">
                  Start with extra caps and supplies, an Overseer’s Office, workshops, and staffed
                  training rooms.
                </span>
                <span v-if="isSurvival" class="text-xs text-warning">
                  Available in Standard mode.
                </span>
              </span>
            </Label>
          </fieldset>
        </template>

        <template v-else>
          <dl
            class="flex flex-col divide-y divide-theme-primary/20 rounded border border-theme-primary/20 bg-surface-sunken px-4"
          >
            <div
              v-for="([label, value], index) in summary"
              :key="label"
              class="flex items-center justify-between gap-4 py-4"
            >
              <dt class="text-sm text-theme-primary/65">{{ label }}</dt>
              <dd
                :class="[
                  index === 0 ? 'text-2xl font-bold' : 'font-semibold',
                  index === 0 ? glowClass : '',
                ]"
              >
                {{ value }}
              </dd>
            </div>
          </dl>
          <p v-if="selectedScenario" class="text-sm leading-6 text-theme-primary/75">
            {{ selectedScenario.description }}
          </p>
          <p
            v-if="!boosted && !selectedScenario?.expedition"
            class="text-sm leading-6 text-theme-primary/75"
          >
            In your vault, start by checking power, food, and water. Open Objectives to see how to
            earn your first recruit.
          </p>
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

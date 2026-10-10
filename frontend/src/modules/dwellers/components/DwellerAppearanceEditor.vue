<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch, type Ref } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import { Input } from '@/core/components/ui/input'
import { Label } from '@/core/components/ui/label'
import { Slider } from '@/core/components/ui/slider'
import { type Dweller, type VisualAttributes } from '../models/dweller'
import { useFeatureFlagsStore } from '../stores/featureFlags'
import { useIdentityOptions } from '../composables/useIdentityOptions'
import { useAppearanceOptions } from '../composables/useAppearanceOptions'
import AppearanceSelect from './appearance/AppearanceSelect.vue'

interface Props {
  dweller: Dweller
  modelValue: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: [attributes: VisualAttributes]
}>()

const featureFlags = useFeatureFlagsStore()
const {
  races: raceOptions,
  statesByRace,
  load: loadIdentityOptions,
  factionsFor,
} = useIdentityOptions()
const {
  skinTonesByRace,
  buildsByRace,
  haircutsByRace,
  headgearByRace,
  expressions,
  poses,
  backgrounds,
  heights,
  eyeColors,
  hairColors,
  loaded: appearanceOptionsLoaded,
  load: loadAppearanceOptions,
} = useAppearanceOptions()
/** True while the form holds defaults set before the feature switch resolved. */
const usedProvisionalDefaults = ref(false)

onMounted(async () => {
  await featureFlags.fetchFlags()
  // The immediate watcher above may have run before the switch landed.
  if (usedProvisionalDefaults.value && featureFlags.factionMechanics && form.faction === 'none') {
    form.faction = 'vault_dweller'
  }
  await loadIdentityOptions()
  await loadAppearanceOptions()
})

// --- Form state ---
// Form controls use strings (and a numeric age), while the API model allows
// null values and represents distinguishing features as an array. Keep that
// transport shape at the save/load boundary rather than leaking it into inputs.
interface AppearanceForm {
  race?: string
  faction?: string
  height?: string
  build?: string
  skin_tone?: string
  eye_color?: string
  age?: number
  state_of_being?: string
  appearance?: string
  hair_style?: string
  hair_color?: string
  facial_hair?: string
  makeup?: string
  expression?: string
  headgear?: string
  distinguishing_features?: string
  clothing_style?: string
  accessory?: string
  object_held?: string
  pose?: string
  background?: string
  voice_line_text?: string
}

type AppearanceSection = 'identity' | 'physical' | 'face' | 'scene'

const sections: Array<{ id: AppearanceSection; label: string; icon: string }> = [
  { id: 'identity', label: 'Identity', icon: 'mdi:badge-account' },
  { id: 'physical', label: 'Build', icon: 'mdi:human' },
  { id: 'face', label: 'Face', icon: 'mdi:face' },
  { id: 'scene', label: 'Scene', icon: 'mdi:backpack' },
]

const form = reactive<AppearanceForm>({})
const activeSection = ref<AppearanceSection>('identity')
const ageValue = computed<number>({
  get: () => form.age ?? 30,
  set: (value) => {
    form.age = value
  },
})

// Initialize form from dweller's current visual_attributes
watch(
  () => props.dweller,
  (dweller) => {
    // Clear any stale keys from previous dweller
    for (const key of Object.keys(form) as Array<keyof AppearanceForm>) {
      delete form[key]
    }
    if (dweller.visual_attributes) {
      for (const [key, value] of Object.entries(dweller.visual_attributes)) {
        if (value === null || value === undefined) continue
        if (key === 'distinguishing_features' && Array.isArray(value)) {
          form.distinguishing_features = value.join(', ')
        } else {
          ;(form as Record<string, string | number | undefined>)[key] = value as string | number
        }
      }
      usedProvisionalDefaults.value = false
    } else {
      // Set defaults. The switch may not have resolved yet, so this is provisional.
      usedProvisionalDefaults.value = true
      form.race = 'human'
      form.faction = featureFlags.factionMechanics ? 'vault_dweller' : 'none'
    }
  },
  { immediate: true, deep: true }
)

// --- Race-filtered computed options ---

const raceKey = computed(() => form.race || 'human')

const availableFactions = computed(() => factionsFor(raceKey.value))

const availableStates = computed(() => statesByRace.value[raceKey.value] ?? null)

const showStateOfBeing = computed(() => form.race && form.race !== 'human')

/** Catalogue keyed by race; falls back to the human entry when a race has no list. */
const forRace = (map: Ref<Record<string, string[]>>) =>
  computed(() => map.value[raceKey.value] || map.value.human || [])

const availableSkinTones = forRace(skinTonesByRace)
const availableBuilds = forRace(buildsByRace)
const availableHaircuts = forRace(haircutsByRace)
const availableHeadgear = forRace(headgearByRace)

/** Reka's Select model is `AcceptableValue`; the form keeps plain strings. */
const setSelect = (key: keyof AppearanceForm, value: unknown) => {
  ;(form as Record<string, unknown>)[key] = value == null ? undefined : String(value)
}

const setAge = (value: number[]) => {
  ageValue.value = value[0] ?? 0
}

const labelClass = 'flex items-center gap-1 text-sm font-medium text-theme-primary/70'
const labelIconClass = 'h-3.5 w-3.5 text-theme-primary/60'

// Pick a random element from an array
function pickRandom<T>(arr: readonly T[] | T[]): T {
  return arr[Math.floor(Math.random() * arr.length)]
}

function randomize() {
  // Both catalogues are fetched on mount; randomising before they land would
  // write undefined into a field and then clear it on save.
  if (raceOptions.value.length === 0 || !appearanceOptionsLoaded.value) return

  const randomRace = pickRandom(raceOptions.value)
  form.race = randomRace

  // Set faction based on race
  form.faction = featureFlags.factionMechanics ? pickRandom(factionsFor(randomRace)) : 'none'

  // State of being for non-humans
  const states = statesByRace.value[randomRace]
  if (states) {
    form.state_of_being = pickRandom(states)
  } else {
    delete form.state_of_being
  }

  // Physical
  form.height = pickRandom(heights.value)
  form.build = pickRandom(buildsByRace.value[randomRace] || buildsByRace.value.human || [])
  form.skin_tone = pickRandom(skinTonesByRace.value[randomRace] || skinTonesByRace.value.human || [])
  form.eye_color = pickRandom(eyeColors.value)
  form.age = Math.floor(Math.random() * 50) + 20

  // Facial
  form.hair_style = pickRandom(haircutsByRace.value[randomRace] || haircutsByRace.value.human || [])
  form.hair_color = pickRandom(hairColors.value)
  form.facial_hair = pickRandom(['None', 'Light Stubble', 'Goatee', 'Moustache', 'Full Beard'])
  if (form.facial_hair === 'None') form.facial_hair = undefined
  form.makeup = pickRandom(['natural', 'glamorous', 'goth'])
  form.expression = pickRandom(expressions.value)
  form.appearance = pickRandom(['attractive', 'cute', 'average', 'unattractive'])
  form.headgear = pickRandom(headgearByRace.value[randomRace] || headgearByRace.value.human || [])

  // Scene
  form.pose = pickRandom(poses.value)
  form.background = pickRandom(backgrounds.value)
}

function handleSave() {
  // Clean up: remove empty values
  const cleaned: VisualAttributes = {}
  for (const [key, value] of Object.entries(form)) {
    if (value !== null && value !== undefined && value !== '') {
      ;(cleaned as Record<string, unknown>)[key] =
        key === 'distinguishing_features' && typeof value === 'string'
          ? value
              .split(',')
              .map((feature) => feature.trim())
              .filter(Boolean)
          : value
    }
  }
  if (!featureFlags.factionMechanics) delete (cleaned as Record<string, unknown>).faction
  // Parent closes the modal after successful save (avoids losing context on failure)
  emit('saved', cleaned)
}

function handleCancel() {
  emit('update:modelValue', false)
}
</script>

<template>
  <TerminalModal
    :open="modelValue"
    title="Edit Appearance"
    size="6xl"
    max-height="90"
    content-class="bg-surface"
    footer-class="flex-shrink-0 border-t border-theme-primary/25 bg-surface-sunken/40 px-5 pt-3 pb-5"
    @update:open="(open) => { if (!open) emit('update:modelValue', false) }"
  >
      <div class="flex-1 overflow-y-auto px-5 pt-5 pb-5">
        <div class="editor-workbench">
          <nav class="section-nav" aria-label="Appearance sections">
            <button
              v-for="section in sections"
              :key="section.id"
              type="button"
              class="section-nav-button"
              :class="{ active: activeSection === section.id }"
              :aria-current="activeSection === section.id ? 'page' : undefined"
              @click="activeSection = section.id"
            >
              <Icon :icon="section.icon" class="section-nav-icon" />
              <span>{{ section.label }}</span>
            </button>
          </nav>

          <div class="editor-scroll">
            <!-- Identity Section -->
            <div v-show="activeSection === 'identity'" class="editor-section">
              <h4 class="section-title">
                <Icon icon="mdi:badge-account" class="section-icon" />
                Identity
              </h4>
              <div class="form-grid">
                <AppearanceSelect
                  id="appearance-race"
                  label="Race"
                  icon="mdi:account"
                  :options="raceOptions"
                  :model-value="form.race"
                  @update:model-value="setSelect('race', $event)"
                />
                <AppearanceSelect
                  v-if="featureFlags.factionMechanics"
                  id="appearance-faction"
                  label="Faction"
                  icon="mdi:shield-account"
                  :options="availableFactions"
                  :model-value="form.faction"
                  @update:model-value="setSelect('faction', $event)"
                />
                <AppearanceSelect
                  v-if="showStateOfBeing"
                  id="appearance-state"
                  label="State of Being"
                  icon="mdi:radioactive"
                  :options="availableStates || []"
                  :model-value="form.state_of_being"
                  @update:model-value="setSelect('state_of_being', $event)"
                />
              </div>
            </div>

            <!-- Physical Section -->
            <div v-show="activeSection === 'physical'" class="editor-section">
              <h4 class="section-title">
                <Icon icon="mdi:human" class="section-icon" />
                Physical
              </h4>
              <div class="form-grid">
                <AppearanceSelect
                  id="appearance-height"
                  label="Height"
                  icon="mdi:human-male-height"
                  :options="heights"
                  :model-value="form.height"
                  @update:model-value="setSelect('height', $event)"
                />
                <AppearanceSelect
                  id="appearance-build"
                  label="Build"
                  icon="mdi:arm-flex"
                  :options="availableBuilds"
                  :model-value="form.build"
                  @update:model-value="setSelect('build', $event)"
                />
                <AppearanceSelect
                  id="appearance-skin-tone"
                  label="Skin Tone"
                  icon="mdi:palette-outline"
                  :options="availableSkinTones"
                  :model-value="form.skin_tone"
                  @update:model-value="setSelect('skin_tone', $event)"
                />
                <AppearanceSelect
                  id="appearance-eye-color"
                  label="Eye Color"
                  icon="mdi:eye-outline"
                  :options="eyeColors"
                  :model-value="form.eye_color"
                  @update:model-value="setSelect('eye_color', $event)"
                />
                <!-- Raw <label> wraps the Age slider (a custom control), not a standalone form label (docs/frontend/RAW_NATIVE_CONTROLS.md). -->
                <label class="flex flex-col gap-1">
                  <span class="flex items-center gap-1 text-sm font-medium text-theme-primary/70">
                    <Icon icon="mdi:calendar-outline" class="h-3.5 w-3.5 text-theme-primary/60" />
                    Age <strong class="ml-auto text-theme-primary">{{ ageValue }}</strong>
                  </span>
                  <!-- @vue-ignore -->
                  <Slider
                    :model-value="[ageValue]"
                    :min="18"
                    :max="80"
                    aria-label="Age"
                    @update:model-value="setAge"
                  />
                  <span class="flex justify-between text-xs text-theme-primary/50"><span>18</span><span>80</span></span>
                </label>
              </div>
            </div>

            <!-- Facial Features Section -->
            <div v-show="activeSection === 'face'" class="editor-section">
              <h4 class="section-title">
                <Icon icon="mdi:face" class="section-icon" />
                Facial Features
              </h4>
              <div class="form-grid">
                <AppearanceSelect
                  id="appearance-hair-style"
                  label="Hair Style"
                  icon="mdi:content-cut"
                  :options="availableHaircuts"
                  :model-value="form.hair_style"
                  @update:model-value="setSelect('hair_style', $event)"
                />
                <AppearanceSelect
                  id="appearance-hair-color"
                  label="Hair Color"
                  icon="mdi:palette"
                  :options="hairColors"
                  :model-value="form.hair_color"
                  @update:model-value="setSelect('hair_color', $event)"
                />
                <div class="form-field">
                  <Label for="appearance-facial-hair" :class="labelClass">
                    <Icon icon="mdi:face-man-outline" :class="labelIconClass" />
                    Facial Hair
                  </Label>
                  <Input
                    id="appearance-facial-hair"
                    v-model="form.facial_hair"
                    placeholder="e.g. beard, stubble"
                  />
                </div>
                <div class="form-field">
                  <Label for="appearance-makeup" :class="labelClass">
                    <Icon icon="mdi:brush-variant" :class="labelIconClass" />
                    Makeup
                  </Label>
                  <Input id="appearance-makeup" v-model="form.makeup" placeholder="e.g. natural, glamorous" />
                </div>
                <AppearanceSelect
                  id="appearance-expression"
                  label="Expression"
                  icon="mdi:emoticon-outline"
                  :options="expressions"
                  :model-value="form.expression"
                  @update:model-value="setSelect('expression', $event)"
                />
                <AppearanceSelect
                  id="appearance-looks"
                  label="Appearance"
                  icon="mdi:account-details-outline"
                  :options="['attractive', 'cute', 'average', 'unattractive']"
                  :model-value="form.appearance"
                  @update:model-value="setSelect('appearance', $event)"
                />
                <div class="form-field form-field-full">
                  <Label for="appearance-features" :class="labelClass">
                    <Icon icon="mdi:star-outline" :class="labelIconClass" />
                    Distinguishing Features
                  </Label>
                  <Input
                    id="appearance-features"
                    v-model="form.distinguishing_features"
                    placeholder="e.g. scar, tattoo, mole"
                  />
                </div>
              </div>
            </div>

            <!-- Equipment Section -->
            <div v-show="activeSection === 'scene'" class="editor-section">
              <h4 class="section-title">
                <Icon icon="mdi:backpack" class="section-icon" />
                Equipment & Scene
              </h4>
              <div class="form-grid">
                <AppearanceSelect
                  id="appearance-headgear"
                  label="Headgear"
                  icon="mdi:hard-hat"
                  :options="availableHeadgear"
                  :model-value="form.headgear"
                  @update:model-value="setSelect('headgear', $event)"
                />
                <div class="form-field">
                  <Label for="appearance-clothing" :class="labelClass">
                    <Icon icon="mdi:tshirt-crew-outline" :class="labelIconClass" />
                    Clothing Style
                  </Label>
                  <Input
                    id="appearance-clothing"
                    v-model="form.clothing_style"
                    placeholder="e.g. casual, military"
                  />
                </div>
                <div class="form-field">
                  <Label for="appearance-accessory" :class="labelClass">
                    <Icon icon="mdi:watch-variant" :class="labelIconClass" />
                    Accessory
                  </Label>
                  <Input id="appearance-accessory" v-model="form.accessory" placeholder="e.g. Pip-Boy" />
                </div>
                <div class="form-field">
                  <Label for="appearance-object" :class="labelClass">
                    <Icon icon="mdi:hand-back-right-outline" :class="labelIconClass" />
                    Object Held
                  </Label>
                  <Input id="appearance-object" v-model="form.object_held" placeholder="e.g. Laser Rifle" />
                </div>
                <AppearanceSelect
                  id="appearance-pose"
                  label="Pose"
                  icon="mdi:human-greeting"
                  :options="poses"
                  :model-value="form.pose"
                  full
                  @update:model-value="setSelect('pose', $event)"
                />
                <AppearanceSelect
                  id="appearance-background"
                  label="Background"
                  icon="mdi:panorama-outline"
                  :options="backgrounds"
                  :model-value="form.background"
                  full
                  @update:model-value="setSelect('background', $event)"
                />
                <div class="form-field form-field-full">
                  <Label for="appearance-voice-line" :class="labelClass">
                    <Icon icon="mdi:comment-quote-outline" :class="labelIconClass" />
                    Voice Line
                  </Label>
                  <Input
                    id="appearance-voice-line"
                    v-model="form.voice_line_text"
                    placeholder="e.g. For the Brotherhood!"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

    <template #footer>
        <div class="editor-footer">
          <Button
            variant="ghost"
            class="utility-button"
            :disabled="raceOptions.length === 0"
            @click="randomize"
          >
            <Icon icon="mdi:dice-5" class="h-4 w-4" />
            Randomize
          </Button>
          <div class="editor-footer-actions">
            <Button variant="ghost" @click="handleCancel">Cancel</Button>
            <Button @click="handleSave">Save Changes</Button>
          </div>
        </div>
    </template>
  </TerminalModal>
</template>

<style scoped>
.editor-workbench {
  display: grid;
  grid-template-columns: 9rem minmax(0, 1fr);
  gap: 1.5rem;
  min-height: 22rem;
}

.section-nav {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.25rem;
  padding-right: 1rem;
  border-right: 1px solid color-mix(in srgb, var(--color-theme-primary) 22%, transparent);
}

.section-nav-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 0.5rem;
  border: 0;
  border-left: 2px solid transparent;
  background: transparent;
  color: color-mix(in srgb, var(--color-theme-primary) 65%, transparent);
  font: inherit;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-align: left;
  cursor: pointer;
}

.section-nav-button:hover,
.section-nav-button:focus-visible {
  background: color-mix(in srgb, var(--color-theme-primary) 8%, transparent);
  color: var(--color-theme-primary);
  outline: none;
}

.section-nav-button.active {
  border-left-color: var(--color-theme-primary);
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.section-nav-icon {
  width: 1rem;
  height: 1rem;
}

.editor-scroll {
  max-height: 55vh;
  overflow-y: auto;
  padding: 0.25rem 0.5rem 0.25rem 0;
}

.editor-scroll::-webkit-scrollbar {
  width: 6px;
}

.editor-scroll::-webkit-scrollbar-thumb {
  background: var(--color-theme-glow);
  border-radius: 3px;
}

.editor-section {
  padding-top: 0.25rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  margin-bottom: 0.75rem;
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.section-icon {
  width: 1.25rem;
  height: 1.25rem;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.form-field-full {
  grid-column: 1 / -1;
}

.editor-workbench :deep(input:not([type='range'])) {
  background: transparent;
  border-color: color-mix(in srgb, var(--color-theme-primary) 32%, transparent);
}

.editor-workbench :deep(input:not([type='range']):focus) {
  background: color-mix(in srgb, var(--color-theme-primary) 7%, transparent);
}

.editor-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  width: 100%;
}

.editor-footer-actions {
  display: flex;
  gap: 0.75rem;
}

.utility-button {
  background: color-mix(in srgb, var(--color-theme-primary) 10%, var(--color-surface));
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 45%, transparent);
}

.utility-button:hover:not(:disabled) {
  background: color-mix(in srgb, var(--color-theme-primary) 18%, var(--color-surface));
  border-color: var(--color-theme-primary);
}

@media (max-width: 36rem) {
  .editor-workbench {
    display: block;
    min-height: 0;
  }

  .section-nav {
    flex-direction: row;
    overflow-x: auto;
    margin-bottom: 1rem;
    padding: 0 0 0.5rem;
    border-right: 0;
    border-bottom: 1px solid color-mix(in srgb, var(--color-theme-primary) 22%, transparent);
  }

  .section-nav-button {
    flex-shrink: 0;
    border-bottom: 2px solid transparent;
    border-left: 0;
  }

  .section-nav-button.active {
    border-bottom-color: var(--color-theme-primary);
  }

  .editor-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .editor-footer-actions {
    justify-content: flex-end;
  }
}
</style>

<script setup lang="ts">
import { audioManager, type AudioBus } from '@/core/audio/audioManager'
import { Label } from '@/core/components/ui/label'
import { Slider } from '@/core/components/ui/slider'
import { Switch } from '@/core/components/ui/switch'

const soundBusOptions: { bus: AudioBus; label: string; description: string }[] = [
  { bus: 'ui', label: 'Interface', description: 'Button clicks, tab switches, popups' },
  { bus: 'sfx', label: 'Game Effects', description: 'Incidents, completions, rewards' },
  { bus: 'music', label: 'Music', description: 'Vault ambient and exploration loops' },
  { bus: 'ambience', label: 'Room Ambience', description: 'Per-room ambience loops' },
]

const toggleSound = () => {
  audioManager.setMuted(!audioManager.muted)
  if (!audioManager.muted) audioManager.play('success', 'ui')
}

const toggleAlarm = () => {
  audioManager.setAlarmEnabled(!audioManager.alarmEnabled)
  if (audioManager.alarmEnabled && !audioManager.muted) audioManager.play('alarm', 'sfx')
}

const setBusVolume = (bus: AudioBus, volume: number) => {
  audioManager.setVolume(bus, volume)
  // Audible feedback: play that bus's sample so the change is heard live.
  if (bus === 'music') audioManager.previewMusic()
  else if (bus === 'ambience') audioManager.previewAmbience()
  else audioManager.play(bus === 'sfx' ? 'success' : 'select', bus)
}
</script>

<template>
  <div>
    <Label
      class="flex cursor-pointer items-center justify-between gap-6 border-b border-theme-primary/10 py-4"
    >
      <div class="flex-1">
        <h4 class="mb-0.5 text-base font-semibold text-theme-primary">Sound Enabled</h4>
        <p class="text-sm text-theme-primary/60">Master switch for all game audio</p>
      </div>
      <Switch
        :checked="audioManager.muted === false"
        :aria-label="audioManager.muted ? 'Enable sound' : 'Disable sound'"
        @update:checked="() => toggleSound()"
      />
    </Label>

    <Label
      class="flex cursor-pointer items-center justify-between gap-6 border-b border-theme-primary/10 py-4"
    >
      <div class="flex-1">
        <h4 class="mb-0.5 text-base font-semibold text-theme-primary">Incident Alarm</h4>
        <p class="text-sm text-theme-primary/60">
          Looping siren while an incident is active; music and effects are unaffected
        </p>
      </div>
      <Switch
        :checked="audioManager.alarmEnabled"
        :disabled="audioManager.muted"
        aria-label="Toggle incident alarm"
        @update:checked="() => toggleAlarm()"
      />
    </Label>

    <div
      v-for="option in soundBusOptions"
      :key="option.bus"
      class="flex items-center justify-between gap-6 border-b border-theme-primary/10 py-4 last:border-b-0"
    >
      <div class="flex-1">
        <h4 class="mb-0.5 text-base font-semibold text-theme-primary">{{ option.label }}</h4>
        <p class="text-sm text-theme-primary/60">{{ option.description }}</p>
      </div>
      <div class="w-40 shrink-0">
        <!-- @vue-ignore -->
        <Slider
          :model-value="[audioManager.volumes[option.bus]]"
          :disabled="audioManager.muted"
          :min="0"
          :max="1"
          :step="0.01"
          :aria-label="`${option.label} volume`"
          @update:model-value="setBusVolume(option.bus, $event[0] ?? 0)"
        />
      </div>
    </div>
  </div>
</template>

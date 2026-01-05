# Visual Effects System

This document describes the configurable visual effects system for the terminal/CRT aesthetic.

## Overview

The application provides three configurable visual effects that create an authentic retro terminal experience:

1. **Flickering** - Screen flicker animation
2. **Scanlines** - Horizontal line overlay
3. **Glow Effects** - Text/element glow with adjustable intensity

All effects can be configured by users via the Preferences page (`/preferences`) and are persisted to localStorage.

## Usage

### In Components

```vue
<script setup lang="ts">
import { inject, ref } from 'vue';

// Inject scanlines state from App.vue
const scanlinesEnabled = inject('scanlines', ref(true));
</script>

<template>
  <div class="my-component">
    <!-- Conditional scanlines overlay -->
    <div v-if="scanlinesEnabled" class="scanlines"></div>

    <!-- Your content here -->
  </div>
</template>
```

### Using the Composable Directly

```ts
import { useVisualEffects } from '@/composables/useVisualEffects';

const {
  flickering,
  scanlines,
  glowIntensity,
  glowClass,
  toggleFlickering,
  toggleScanlines,
  setGlowIntensity
} = useVisualEffects();

// Toggle effects
toggleFlickering();
toggleScanlines();

// Set glow intensity
setGlowIntensity('subtle'); // 'off' | 'subtle' | 'normal' | 'strong'
```

## CSS Classes

### Scanlines
```css
.scanlines {
  /* Always-on scanline overlay */
  /* No conditional classes needed - use v-if in template */
}
```

### Flickering
```css
.flicker {
  /* Apply to elements that should flicker */
  animation: flicker 0.15s infinite;
}
```

### Glow Effects
```css
.terminal-glow-subtle {
  /* Minimal glow - good for readability */
}

.terminal-glow {
  /* Standard CRT glow (default) */
}

.terminal-glow-strong {
  /* Maximum retro aesthetics */
}
```

Use the `glowClass` computed property for dynamic glow:

```vue
<template>
  <h1 :class="glowClass">Glowing Text</h1>
</template>
```

## Configuration Page

Users can configure all visual effects at `/preferences`:

- **Theme Selection**: Choose from FO3 (teal), FNV (amber), FO4 (green)
- **Flickering Toggle**: Enable/disable screen flicker
- **Scanlines Toggle**: Enable/disable horizontal lines
- **Glow Intensity**: Off / Subtle / Normal / Strong

All settings are automatically saved to localStorage.

## Accessibility

Visual effects can be completely disabled for:
- Motion sensitivity (flickering)
- Performance on low-end devices
- Personal preference

Use the "Disable All Effects" button in preferences for accessibility mode.

## Implementation Checklist

When adding scanlines to a new component:

1. **Import inject and ref**:
   ```ts
   import { inject, ref } from 'vue';
   ```

2. **Inject scanlines state**:
   ```ts
   const scanlinesEnabled = inject('scanlines', ref(true));
   ```

3. **Make scanlines conditional**:
   ```vue
   <div v-if="scanlinesEnabled" class="scanlines"></div>
   ```

## Components with Scanlines

The following components currently use scanlines:

- VaultView.vue ✅ (updated)
- DwellersView.vue
- DwellerDetailView.vue
- RelationshipsView.vue
- QuestsView.vue
- ObjectivesView.vue
- RadioView.vue
- HomeView.vue
- LoginFormTerminal.vue
- RegisterForm.vue
- DwellerChat.vue
- LevelUpNotification.vue

## API Reference

### useVisualEffects()

Returns an object with:

**State:**
- `flickering` (ComputedRef<boolean>) - Flickering enabled
- `scanlines` (ComputedRef<boolean>) - Scanlines enabled
- `glowIntensity` (ComputedRef<EffectIntensity>) - Current glow level
- `isGlowEnabled` (ComputedRef<boolean>) - Whether glow is on
- `glowClass` (ComputedRef<string>) - CSS class for current glow intensity
- `currentConfig` (ComputedRef<VisualEffectsConfig>) - All settings as object

**Actions:**
- `toggleFlickering()` - Toggle flicker on/off
- `toggleScanlines()` - Toggle scanlines on/off
- `setGlowIntensity(intensity: EffectIntensity)` - Set glow level
- `toggleGlow()` - Cycle through glow intensities
- `enableAllEffects()` - Turn all effects on (normal intensity)
- `disableAllEffects()` - Turn all effects off (accessibility mode)
- `resetToDefaults()` - Reset to default settings

### Types

```ts
type EffectIntensity = 'off' | 'subtle' | 'normal' | 'strong'

interface VisualEffectsConfig {
  flickering: boolean
  scanlines: boolean
  glow: EffectIntensity
}
```

## localStorage Keys

- `visual-effects:flickering` - boolean
- `visual-effects:scanlines` - boolean
- `visual-effects:glow` - EffectIntensity

## Migration from useFlickering

The old `useFlickering` composable has been replaced by `useVisualEffects`. For backward compatibility:

```ts
// Old way (still works)
const { isFlickering, toggleFlickering } = inject(...)

// New way (recommended)
import { useVisualEffects } from '@/composables/useVisualEffects'
const { flickering, toggleFlickering } = useVisualEffects()
```

Both are provided by App.vue for compatibility.

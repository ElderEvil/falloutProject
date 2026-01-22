# UI Component Library

Terminal-themed UI components for the Fallout Shelter Vue 3 application.

## Overview

This library provides pre-styled, reusable components that follow the Fallout terminal aesthetic with terminal green colors, CRT effects, and retro styling.

## Components

### UButton

Terminal-themed button with variants and sizes.

**Props:**
- `variant`: 'primary' | 'secondary' | 'danger' | 'ghost' (default: 'primary')
- `size`: 'xs' | 'sm' | 'md' | 'lg' | 'xl' (default: 'md')
- `disabled`: boolean (default: false)
- `loading`: boolean (default: false)
- `icon`: Component (optional)
- `iconRight`: Component (optional)
- `block`: boolean (default: false)

**Events:**
- `@click`: Emitted on button click

**Usage:**
```vue
<UButton variant="primary" size="md" @click="handleClick">
  Click Me
</UButton>

<UButton variant="secondary" :icon="PlusIcon">
  Add Item
</UButton>

<UButton variant="danger" :loading="isDeleting">
  Delete
</UButton>
```

### UInput

Terminal-themed input field with label and error support.

**Props:**
- `modelValue`: string | number
- `type`: 'text' | 'email' | 'password' | 'number' | 'tel' | 'url' (default: 'text')
- `label`: string (optional)
- `placeholder`: string (optional)
- `helpText`: string (optional)
- `error`: string (optional)
- `required`: boolean (default: false)
- `disabled`: boolean (default: false)
- `icon`: Component (optional)
- `iconRight`: Component (optional)
- `size`: 'sm' | 'md' | 'lg' (default: 'md')

**Events:**
- `@update:modelValue`: Emitted on value change
- `@blur`: Emitted on blur
- `@focus`: Emitted on focus

**Usage:**
```vue
<UInput
  v-model="email"
  type="email"
  label="Email Address"
  placeholder="user@vault.com"
  :icon="EnvelopeIcon"
  required
/>

<UInput
  v-model="password"
  type="password"
  label="Password"
  :error="passwordError"
/>
```

### UCard

Terminal-themed card container.

**Props:**
- `title`: string (optional)
- `padding`: 'none' | 'sm' | 'md' | 'lg' | 'xl' (default: 'md')
- `glow`: boolean (default: false)
- `crt`: boolean (default: false)
- `bordered`: boolean (default: true)

**Slots:**
- `header`: Custom header content
- `default`: Main content
- `footer`: Footer content

**Usage:**
```vue
<UCard title="Vault Stats" glow crt>
  <p>Population: 42</p>
  <p>Happiness: 85%</p>

  <template #footer>
    <UButton>View Details</UButton>
  </template>
</UCard>
```

### UModal

Terminal-themed modal dialog.

**Props:**
- `modelValue`: boolean (required)
- `title`: string (optional)
- `size`: 'sm' | 'md' | 'lg' | 'xl' | 'full' (default: 'md')
- `closeOnEscape`: boolean (default: true)
- `closeOnClickOutside`: boolean (default: true)

**Events:**
- `@update:modelValue`: Emitted when modal visibility changes
- `@close`: Emitted when modal closes

**Slots:**
- `header`: Custom header
- `default`: Main content
- `footer`: Footer with actions

**Usage:**
```vue
<UModal v-model="isOpen" title="Confirm Action" size="md">
  <p>Are you sure you want to delete this vault?</p>

  <template #footer>
    <UButton variant="secondary" @click="isOpen = false">Cancel</UButton>
    <UButton variant="danger" @click="handleDelete">Delete</UButton>
  </template>
</UModal>
```

### UBadge

Terminal-themed badge/tag component.

**Props:**
- `variant`: 'success' | 'warning' | 'danger' | 'info' | 'default' (default: 'default')
- `size`: 'sm' | 'md' | 'lg' (default: 'md')
- `icon`: Component (optional)
- `dot`: boolean (default: false)

**Usage:**
```vue
<UBadge variant="success">Active</UBadge>
<UBadge variant="warning" dot>Pending</UBadge>
<UBadge variant="danger" :icon="ExclamationIcon">Error</UBadge>
```

### UAlert

Terminal-themed alert/notification component.

**Props:**
- `variant`: 'success' | 'warning' | 'danger' | 'info' (default: 'info')
- `title`: string (optional)
- `dismissible`: boolean (default: false)
- `icon`: Component (optional)

**Events:**
- `@close`: Emitted when alert is dismissed

**Usage:**
```vue
<UAlert variant="success" title="Success" :icon="CheckIcon" dismissible>
  Vault created successfully!
</UAlert>

<UAlert variant="danger" title="Error">
  Failed to connect to server.
</UAlert>
```

### UTooltip

Terminal-themed tooltip.

**Props:**
- `text`: string (required)
- `position`: 'top' | 'bottom' | 'left' | 'right' (default: 'top')
- `delay`: number (default: 200ms)

**Usage:**
```vue
<UTooltip text="Click to build a new room">
  <UButton>Build</UButton>
</UTooltip>
```

### UDropdown

Terminal-themed dropdown menu.

**Props:**
- `position`: 'left' | 'right' (default: 'right')

**Slots:**
- `trigger`: Element that triggers the dropdown
- `default`: Dropdown content

**Usage:**
```vue
<UDropdown position="right">
  <template #trigger>
    <UButton>Menu</UButton>
  </template>

  <div class="px-4 py-2 hover:bg-surfaceLight cursor-pointer">Option 1</div>
  <div class="px-4 py-2 hover:bg-surfaceLight cursor-pointer">Option 2</div>
  <div class="px-4 py-2 hover:bg-surfaceLight cursor-pointer">Option 3</div>
</UDropdown>
```

## Importing Components

### Single Import
```vue
<script setup lang="ts">
import { UButton } from '@/components/ui'
</script>
```

### Multiple Imports
```vue
<script setup lang="ts">
import { UButton, UInput, UCard } from '@/components/ui'
</script>
```

## Customization

All components use Tailwind v4 design tokens from `src/assets/tailwind.css`. To customize:

1. Edit the @theme section in `tailwind.css`
2. Components will automatically pick up the new values
3. See `STYLEGUIDE.md` for complete design token reference

## Accessibility

All components follow WCAG 2.1 AA standards:
- Keyboard navigation support
- Proper ARIA labels
- Focus indicators
- Screen reader compatibility

## Examples

See `frontend/STYLEGUIDE.md` for comprehensive examples and best practices.

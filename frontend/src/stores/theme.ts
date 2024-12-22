import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Theme, ThemeVariant } from '@/types/theme'

const THEMES: Theme[] = [
  {
    id: 'pip-boy',
    name: 'PIP-BOY',
    colors: {
      primary: '#00ff00',
      background: '#000000',
      border: '#00ff00',
      text: '#00ff00',
      textSecondary: '#00cc00',
      hover: '#00cc00',
      pressed: '#009900',
      shadow: 'rgba(0, 255, 0, 0.3)',
      modalShadow: '0 0 20px rgba(0, 255, 0, 0.5), 0 0 40px rgba(0, 255, 0, 0.3)'
    }
  },
  {
    id: 'terminal',
    name: 'TERMINAL',
    colors: {
      primary: '#2ecc71',
      background: '#0a0a0a',
      border: '#2ecc71',
      text: '#2ecc71',
      textSecondary: '#27ae60',
      hover: '#27ae60',
      pressed: '#219a52',
      shadow: 'rgba(46, 204, 113, 0.3)',
      modalShadow: '0 0 20px rgba(46, 204, 113, 0.5), 0 0 40px rgba(46, 204, 113, 0.3)'
    }
  },
  {
    id: 'fallout3',
    name: 'FALLOUT 3',
    colors: {
      primary: '#4CAF50',
      background: '#001800',
      border: '#4CAF50',
      text: '#4CAF50',
      textSecondary: '#388E3C',
      hover: '#388E3C',
      pressed: '#2E7D32',
      shadow: 'rgba(76, 175, 80, 0.3)',
      modalShadow: '0 0 20px rgba(76, 175, 80, 0.5), 0 0 40px rgba(76, 175, 80, 0.3)'
    }
  },
  {
    id: 'new-vegas',
    name: 'NEW VEGAS',
    colors: {
      primary: '#FFA726',
      background: '#180F00',
      border: '#FFA726',
      text: '#FFA726',
      textSecondary: '#FB8C00',
      hover: '#FB8C00',
      pressed: '#F57C00',
      shadow: 'rgba(255, 167, 38, 0.3)',
      modalShadow: '0 0 20px rgba(255, 167, 38, 0.5), 0 0 40px rgba(255, 167, 38, 0.3)'
    }
  }
]

export const useThemeStore = defineStore('theme', () => {
  const currentTheme = ref<ThemeVariant>('terminal')

  const theme = computed(() => THEMES.find((t) => t.id === currentTheme.value) || THEMES[0])

  const themeOverrides = computed(() => ({
    common: {
      primaryColor: theme.value.colors.primary,
      primaryColorHover: theme.value.colors.hover,
      primaryColorPressed: theme.value.colors.pressed,
      baseColor: theme.value.colors.background,
      textColorBase: theme.value.colors.text,
      textColor2: theme.value.colors.textSecondary,
      bodyColor: theme.value.colors.background,
      modalColor: theme.value.colors.background
    },
    Card: {
      color: theme.value.colors.background,
      borderRadius: '2px',
      textColor: theme.value.colors.text,
      titleTextColor: theme.value.colors.text,
      titleFontWeight: '800',
      borderColor: theme.value.colors.border,
      fontWeight: '600',
      boxShadow: theme.value.colors.modalShadow
    },
    Button: {
      textColor: theme.value.colors.text,
      fontWeight: '600',
      border: `2px solid ${theme.value.colors.border}`,
      borderHover: `2px solid ${theme.value.colors.hover}`,
      borderPressed: `2px solid ${theme.value.colors.pressed}`,
      colorHover: theme.value.colors.background,
      colorPressed: theme.value.colors.background,
      colorFocus: theme.value.colors.background,
      textColorHover: theme.value.colors.hover,
      textColorPressed: theme.value.colors.pressed,
      textColorFocus: theme.value.colors.hover,
      color: theme.value.colors.background
    },
    Modal: {
      color: theme.value.colors.background,
      textColor: theme.value.colors.text,
      titleTextColor: theme.value.colors.text,
      titleFontWeight: '800',
      padding: '24px',
      titleFontSize: '18px',
      borderRadius: '2px',
      boxShadow: theme.value.colors.modalShadow,
      borderColor: theme.value.colors.border
    },
    Dialog: {
      color: theme.value.colors.background,
      textColor: theme.value.colors.text,
      titleTextColor: theme.value.colors.text,
      titleFontWeight: '800',
      iconColor: theme.value.colors.text,
      boxShadow: theme.value.colors.modalShadow,
      borderColor: theme.value.colors.border
    },
    Dropdown: {
      color: theme.value.colors.background,
      optionTextColor: theme.value.colors.text,
      optionTextColorActive: theme.value.colors.hover,
      optionColorHover: 'rgba(0, 0, 0, 0.3)',
      dividerColor: theme.value.colors.border,
      boxShadow: theme.value.colors.modalShadow
    },
    Select: {
      color: theme.value.colors.background,
      peers: {
        InternalSelection: {
          textColor: theme.value.colors.text,
          placeholderColor: theme.value.colors.textSecondary,
          borderFocus: `2px solid ${theme.value.colors.border}`,
          borderHover: `2px solid ${theme.value.colors.hover}`,
          border: `2px solid ${theme.value.colors.border}`,
          borderActive: `2px solid ${theme.value.colors.pressed}`
        },
        InternalSelectMenu: {
          color: theme.value.colors.background,
          optionTextColor: theme.value.colors.text,
          optionTextColorActive: theme.value.colors.hover,
          optionColorHover: 'rgba(0, 0, 0, 0.3)',
          boxShadow: theme.value.colors.modalShadow
        }
      }
    },
    Form: {
      labelTextColor: theme.value.colors.text,
      asteriskColor: theme.value.colors.text
    }
  }))

  function setTheme(newTheme: ThemeVariant) {
    currentTheme.value = newTheme
  }

  return {
    currentTheme,
    theme,
    themeOverrides,
    setTheme,
    availableThemes: THEMES
  }
})

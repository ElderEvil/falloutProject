import './assets/tailwind.css' // Tailwind CSS should be imported first
import './assets/main.css' // Custom styles should be imported after

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { MotionPlugin } from '@vueuse/motion'
import App from './App.vue'
import router from './router'
import {
  UAlert,
  UBadge,
  UButton,
  UCard,
  UInput,
  UModal,
  UProgressBar,
  USelect,
  USkeleton,
  UTabs,
  UTooltip,
} from '@/core/components/ui'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(MotionPlugin)

for (const [name, component] of Object.entries({
  UAlert,
  UBadge,
  UButton,
  UCard,
  UInput,
  UModal,
  UProgressBar,
  USelect,
  USkeleton,
  UTabs,
  UTooltip,
})) {
  app.component(name, component)
}

app.mount('#app')

import './assets/tailwind.css' // Tailwind CSS should be imported first
import './assets/main.css' // Custom styles should be imported after

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { initializeDesktop } from '@/core/utils/desktop'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
void initializeDesktop()

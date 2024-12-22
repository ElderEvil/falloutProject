import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from '../../../../Downloads/project-bolt-sb1-hubjsk (4)/project/src/router'
import App from './App.vue'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')

import { createApp } from 'vue'
import {
  ElAlert,
  ElAside,
  ElButton,
  ElCard,
  ElContainer,
  ElForm,
  ElFormItem,
  ElHeader,
  ElInput,
  ElMain,
  ElMenu,
  ElMenuItem,
  ElResult
} from 'element-plus'
import 'element-plus/dist/index.css'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { setUnauthorizedHandler } from './utils/request'
import './styles/index.css'

const app = createApp(App)
const pinia = createPinia()
const elementComponents = [
  ElAlert,
  ElAside,
  ElButton,
  ElCard,
  ElContainer,
  ElForm,
  ElFormItem,
  ElHeader,
  ElInput,
  ElMain,
  ElMenu,
  ElMenuItem,
  ElResult
]

app.use(pinia)
app.use(router)
elementComponents.forEach(component => app.component(component.name, component))

setUnauthorizedHandler(async () => {
  useAuthStore(pinia).clearSession()
  if (router.currentRoute.value.name !== 'login') {
    await router.replace({
      name: 'login',
      query: { redirect: router.currentRoute.value.fullPath }
    })
  }
})

app.mount('#app')

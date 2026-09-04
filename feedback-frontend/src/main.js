import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { setUnauthorizedHandler } from './utils/request'
import './styles/index.css'
import './styles/workspace.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn })

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

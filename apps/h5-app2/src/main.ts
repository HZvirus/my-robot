import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { ensureAuth } from './utils/auth'
import './assets/main.css'

// 启动即注册设备令牌，避免首个鉴权请求额外等待
void ensureAuth()

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')

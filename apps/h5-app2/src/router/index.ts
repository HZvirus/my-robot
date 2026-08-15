import { createRouter, createWebHistory } from 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    /** TTS 流式合成传输层：ws-direct = 浏览器直连讯飞；缺省走后端 WS 桥接 */
    ttsTransport?: 'ws-direct'
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue')
    },
    {
      path: '/companion',
      name: 'companion',
      component: () => import('@/views/CompanionView.vue')
    },
    {
      path: '/companion/smart',
      name: 'companion-smart',
      component: () => import('@/views/CompanionSmartView.vue')
    },
    {
      path: '/companion/fast',
      name: 'companion-fast',
      meta: { ttsTransport: 'ws-direct' },
      component: () => import('@/views/CompanionFastView.vue')
    },
    {
      path: '/science',
      name: 'science',
      component: () => import('@/views/ScienceView.vue')
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue')
    }
  ]
})

export default router

import { createRouter, createWebHistory } from 'vue-router'

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
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue')
    }
  ]
})

export default router

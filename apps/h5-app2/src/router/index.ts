import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'companion-fast',
      component: () => import('@/views/CompanionFastView.vue')
    }
  ]
})

export default router

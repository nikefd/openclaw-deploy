import { createRouter, createWebHistory } from 'vue-router'
import HelloView from '@/views/HelloView.vue'

export const router = createRouter({
  history: createWebHistory('/v2/'),
  routes: [
    {
      path: '/',
      name: 'hello',
      component: HelloView,
    },
  ],
})

export default router

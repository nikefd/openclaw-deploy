import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '@/views/ChatView.vue'
import HelloView from '@/views/HelloView.vue'

export const router = createRouter({
  history: createWebHistory('/v2/'),
  routes: [
    { path: '/', name: 'chat-root', component: ChatView },
    { path: '/c/:sid', name: 'chat', component: ChatView },
    {
      path: '/login',
      name: 'login',
      // Phase D will replace with a real auth view.
      component: () => import('@/views/ChatView.vue'),
    },
    { path: '/hello', name: 'hello', component: HelloView },
    // Phase D2 — auxiliary pages.
    { path: '/tasks', name: 'tasks', component: () => import('@/views/TasksView.vue') },
    { path: '/usage', name: 'usage', component: () => import('@/views/UsageView.vue') },
    { path: '/architecture', name: 'architecture', component: () => import('@/views/ArchitectureView.vue') },
  ],
})

export default router

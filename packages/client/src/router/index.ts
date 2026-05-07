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
    // Phase D1 — agents hub + sub-views.
    { path: '/agents', name: 'agents', component: () => import('@/views/AgentsView.vue') },
    { path: '/agents/finance', name: 'agents-finance', component: () => import('@/views/agents/FinanceView.vue') },
    { path: '/agents/climbing', name: 'agents-climbing', component: () => import('@/views/agents/ClimbingView.vue') },
    { path: '/agents/interview', name: 'agents-interview', component: () => import('@/views/agents/InterviewView.vue') },
    { path: '/agents/ai-frontier', name: 'agents-ai-frontier', component: () => import('@/views/agents/AiFrontierView.vue') },
    // Phase D2 — auxiliary pages.
    { path: '/tasks', name: 'tasks', component: () => import('@/views/TasksView.vue') },
    { path: '/usage', name: 'usage', component: () => import('@/views/UsageView.vue') },
    { path: '/architecture', name: 'architecture', component: () => import('@/views/ArchitectureView.vue') },
    // Phase D3 — files browser & perf monitor
    { path: '/files', name: 'files', component: () => import('@/views/FilesView.vue') },
    { path: '/perf', name: 'perf', component: () => import('@/views/PerfView.vue') },
  ],
})

export default router

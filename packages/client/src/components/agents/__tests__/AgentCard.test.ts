import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import AgentCard from '@/components/agents/AgentCard.vue'

const pushSpy = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushSpy }),
}))

describe('AgentCard', () => {
  it('renders emoji, name, description, and recent', () => {
    const w = mount(AgentCard, {
      props: {
        emoji: '💰',
        name: 'Finance',
        description: 'A股盯盘',
        status: 'active',
        recent: '今日 +2%',
        to: '/agents/finance',
      },
    })
    expect(w.text()).toContain('💰')
    expect(w.text()).toContain('Finance')
    expect(w.text()).toContain('A股盯盘')
    expect(w.text()).toContain('今日 +2%')
    expect(w.find('.status').classes()).toContain('active')
  })

  it('triggers router.push on click', async () => {
    pushSpy.mockClear()
    const w = mount(AgentCard, {
      props: {
        emoji: '🧗',
        name: 'Climb',
        description: 'd',
        status: 'paused',
        to: '/agents/climbing',
      },
    })
    await w.trigger('click')
    expect(pushSpy).toHaveBeenCalledWith('/agents/climbing')
  })

  it('triggers router.push on Enter key', async () => {
    pushSpy.mockClear()
    const w = mount(AgentCard, {
      props: {
        emoji: '🧗',
        name: 'Climb',
        description: 'd',
        status: 'gray',
        to: '/foo',
      },
    })
    await w.trigger('keydown', { key: 'Enter' })
    expect(pushSpy).toHaveBeenCalledWith('/foo')
  })
})

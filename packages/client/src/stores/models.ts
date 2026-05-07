// stores/models.ts — selectable LLM models. Phase C2 stub list; Phase E will
// fetch from /api/models. ModelDropdown reads `current` and writes via
// setCurrent(); other components subscribe to `current`.
import { defineStore } from 'pinia'

export interface ModelOption {
  id: string
  name: string
  provider: string
  /** emoji used as a stand-in for a real provider logo */
  icon: string
  contextWindow: number
  /** USD per 1M input tokens (display only) */
  pricePerMTokIn: number
  pricePerMTokOut: number
}

const STUB_MODELS: ModelOption[] = [
  {
    id: 'claude-opus-4.7',
    name: 'Claude Opus 4.7',
    provider: 'anthropic',
    icon: '🟧',
    contextWindow: 200_000,
    pricePerMTokIn: 15,
    pricePerMTokOut: 75,
  },
  {
    id: 'claude-sonnet-4',
    name: 'Claude Sonnet 4',
    provider: 'anthropic',
    icon: '🟧',
    contextWindow: 200_000,
    pricePerMTokIn: 3,
    pricePerMTokOut: 15,
  },
  {
    id: 'gpt-5',
    name: 'GPT-5',
    provider: 'openai',
    icon: '🟢',
    contextWindow: 256_000,
    pricePerMTokIn: 5,
    pricePerMTokOut: 20,
  },
  {
    id: 'gemini-2.5-flash',
    name: 'Gemini 2.5 Flash',
    provider: 'google',
    icon: '🟦',
    contextWindow: 1_000_000,
    pricePerMTokIn: 0.3,
    pricePerMTokOut: 1.2,
  },
  {
    id: 'glm-5',
    name: 'GLM-5',
    provider: 'zhipu',
    icon: '🟪',
    contextWindow: 128_000,
    pricePerMTokIn: 0.5,
    pricePerMTokOut: 1.5,
  },
]

export const useModelsStore = defineStore('models', {
  state: () => ({
    list: STUB_MODELS as ModelOption[],
    currentId: STUB_MODELS[0]!.id,
  }),
  getters: {
    current(state): ModelOption {
      return state.list.find((m) => m.id === state.currentId) ?? state.list[0]!
    },
  },
  actions: {
    setCurrent(id: string) {
      if (this.list.some((m) => m.id === id)) {
        this.currentId = id
      }
    },
    setList(list: ModelOption[]) {
      this.list = list
      if (!list.some((m) => m.id === this.currentId) && list[0]) {
        this.currentId = list[0].id
      }
    },
  },
})

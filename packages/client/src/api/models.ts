// api/models.ts — Phase C2 stub. Phase E will fetch /api/models from the
// gateway. For now we just hand back what stores/models.ts already seeded so
// that the Models pinia store can be re-hydrated through the same code path.
//
// ⚠️ Reconstructed by Phase C1 after an accidental move-collision while
// stashing C2 files for typecheck isolation. The shape (async fetchModels()
// returning ModelOption[]) matches what was previously here. If C2 had a
// different signature, please overwrite.
import type { ModelOption } from '@/stores/models'

export async function fetchModels(): Promise<ModelOption[]> {
  await new Promise((r) => setTimeout(r, 50))
  return [
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
}

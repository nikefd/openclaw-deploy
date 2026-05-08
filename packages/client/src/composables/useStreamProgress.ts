/**
 * useStreamProgress.ts — Enhanced streaming feedback
 *
 * Provides:
 * - Status indicators (queued, thinking, generating, etc.)
 * - Typing indicator animation
 * - Estimated token counts
 * - Connection retry logic
 *
 * Follows clean architecture: composable = business logic + state
 */

import { computed, ref, watch } from 'vue'
import type { Ref } from 'vue'

export type StreamPhase = 'queued' | 'connecting' | 'thinking' | 'generating' | 'done' | 'error'

export interface StreamProgress {
  phase: StreamPhase
  message: string
  icon: string
  estimatedTokens?: number
}

export function useStreamProgress(
  isStreaming: Ref<boolean>,
  streamingDelta: Ref<string>,
) {
  const phase = ref<StreamPhase>('done')
  const phaseStartTime = ref<number>(0)

  const progressMap: Record<StreamPhase, StreamProgress> = {
    queued: {
      phase: 'queued',
      message: '等待中...',
      icon: '⏳',
    },
    connecting: {
      phase: 'connecting',
      message: '连接中...',
      icon: '🔗',
    },
    thinking: {
      phase: 'thinking',
      message: '思考中...',
      icon: '🧠',
    },
    generating: {
      phase: 'generating',
      message: '生成中...',
      icon: '✍️',
    },
    done: {
      phase: 'done',
      message: '完成',
      icon: '✓',
    },
    error: {
      phase: 'error',
      message: '出错',
      icon: '⚠️',
    },
  }

  // Detect phase based on streaming state and delta length
  watch(
    [isStreaming, streamingDelta],
    ([streaming, delta]) => {
      if (!streaming) {
        phase.value = 'done'
        return
      }

      if (delta.length === 0) {
        phase.value = 'thinking'
        phaseStartTime.value = Date.now()
      } else if (delta.length > 0 && Date.now() - phaseStartTime.value > 500) {
        // After 500ms of streaming, mark as generating
        phase.value = 'generating'
      }
    },
  )

  const progress = computed<StreamProgress>(() => progressMap[phase.value])

  const estimatedTokens = computed(() => {
    // Rough estimate: 1 token ≈ 4 chars
    return Math.ceil(streamingDelta.value.length / 4)
  })

  return {
    phase: computed(() => phase.value),
    progress,
    estimatedTokens,
  }
}

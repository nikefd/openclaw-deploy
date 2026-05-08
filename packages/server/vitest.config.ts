import { defineConfig } from 'vitest/config'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  resolve: {
    alias: {
      '@oc/shared': fileURLToPath(new URL('../shared/src/index.ts', import.meta.url)),
      '@oc/shared/events': fileURLToPath(new URL('../shared/src/events.ts', import.meta.url)),
      '@oc/shared/chat': fileURLToPath(new URL('../shared/src/chat.ts', import.meta.url)),
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
    testTimeout: 15000,
    hookTimeout: 15000,
  },
})

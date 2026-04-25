// telemetry.js — fire-and-forget perf / log calls. Never throw.

import { config } from './config.js';

export function perfLog(type, durationMs, extra) {
  try {
    fetch(config.api.perfLog, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type,
        durationMs: Math.round(durationMs || 0),
        ...(extra || {}),
      }),
      keepalive: true,
    }).catch(() => {});
  } catch {}
}

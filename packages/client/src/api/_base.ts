// Phase E: API base path resolver.
// In v2, all backend calls go through `/v2/api/` to avoid colliding with
// the legacy stack's `/api/*` namespace (which is locked to /var/www/chat
// on the same domain). The vite dev server proxies `/v2/api` to :8001.
const BASE = (import.meta.env.VITE_API_BASE ?? '/v2/api') as string

export function apiUrl(path: string): string {
  // Accepts "memory/list", "/memory/list", or "/api/memory/list".
  let p = path.startsWith('/api/') ? path.slice(4) : path
  if (!p.startsWith('/')) p = '/' + p
  return BASE + p
}

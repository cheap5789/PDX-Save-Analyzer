/**
 * useApi — thin wrapper around fetch for the PDX backend REST API.
 * All functions return { data, error } or throw on network failure.
 */

const BASE = ''  // proxied through Vite dev server

async function request(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body) opts.body = JSON.stringify(body)
  const res = await fetch(`${BASE}${path}`, opts)
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const msg = data?.detail || `${res.status} ${res.statusText}`
    throw new Error(msg)
  }
  return data
}

export function useApi() {
  return {
    /** GET /api/status */
    getStatus: () => request('GET', '/api/status'),

    /** POST /api/start — launch watcher pipeline */
    start: (config) => request('POST', '/api/start', config),

    /** POST /api/stop — stop watcher pipeline */
    stop: () => request('POST', '/api/stop'),

    /** GET /api/fields?category= */
    getFields: (category = null) => {
      const q = category ? `?category=${encodeURIComponent(category)}` : ''
      return request('GET', `/api/fields${q}`)
    },

    /** GET /api/playthroughs?game= */
    getPlaythroughs: (game = null) => {
      const q = game ? `?game=${encodeURIComponent(game)}` : ''
      return request('GET', `/api/playthroughs${q}`)
    },

    /** GET /api/snapshots/:id?limit=&after= */
    getSnapshots: (playthroughId, { limit, after } = {}) => {
      const params = new URLSearchParams()
      if (limit) params.set('limit', limit)
      if (after) params.set('after', after)
      const q = params.toString() ? `?${params}` : ''
      return request('GET', `/api/snapshots/${playthroughId}${q}`)
    },

    /** GET /api/events/:id?event_type=&limit= */
    getEvents: (playthroughId, { event_type, limit } = {}) => {
      const params = new URLSearchParams()
      if (event_type) params.set('event_type', event_type)
      if (limit) params.set('limit', limit)
      const q = params.toString() ? `?${params}` : ''
      return request('GET', `/api/events/${playthroughId}${q}`)
    },

    /** PATCH /api/events/:id/note — set or update AAR note */
    updateAarNote: (eventId, note) =>
      request('PATCH', `/api/events/${eventId}/note`, { note }),

    /** GET /api/config?game= — load persisted config */
    getConfig: (game = 'eu5') => request('GET', `/api/config?game=${encodeURIComponent(game)}`),

    /** POST /api/config — save config without starting pipeline */
    saveConfig: (config) => request('POST', '/api/config', config),

    /** POST /api/load-playthrough — open DB for browsing */
    loadPlaythrough: (game, playthroughId) =>
      request('POST', '/api/load-playthrough', { game, playthrough_id: playthroughId }),
  }
}

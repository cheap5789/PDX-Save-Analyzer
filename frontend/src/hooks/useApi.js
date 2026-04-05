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

    // ── Religions ───────────────────────────────────────────────
    /** GET /api/religions/:id — static religion records */
    getReligions: (playthroughId) =>
      request('GET', `/api/religions/${playthroughId}`),

    /** GET /api/religions/:id/snapshots?religion_id= */
    getReligionSnapshots: (playthroughId, { religion_id } = {}) => {
      const params = new URLSearchParams()
      if (religion_id != null) params.set('religion_id', religion_id)
      const q = params.toString() ? `?${params}` : ''
      return request('GET', `/api/religions/${playthroughId}/snapshots${q}`)
    },

    // ── Wars ────────────────────────────────────────────────────
    /** GET /api/wars/:id?active_only= */
    getWars: (playthroughId, { active_only } = {}) => {
      const params = new URLSearchParams()
      if (active_only) params.set('active_only', 'true')
      const q = params.toString() ? `?${params}` : ''
      return request('GET', `/api/wars/${playthroughId}${q}`)
    },

    /** GET /api/wars/:id/snapshots?war_id= */
    getWarSnapshots: (playthroughId, { war_id } = {}) => {
      const params = new URLSearchParams()
      if (war_id) params.set('war_id', war_id)
      const q = params.toString() ? `?${params}` : ''
      return request('GET', `/api/wars/${playthroughId}/snapshots${q}`)
    },

    /** GET /api/wars/:id/participants?war_id= */
    getWarParticipants: (playthroughId, { war_id } = {}) => {
      const params = new URLSearchParams()
      if (war_id) params.set('war_id', war_id)
      const q = params.toString() ? `?${params}` : ''
      return request('GET', `/api/wars/${playthroughId}/participants${q}`)
    },

    // ── Geography ───────────────────────────────────────────────
    /** GET /api/locations/:id/snapshots?snapshot_id=&owner_id=&location_id= */
    getLocationSnapshots: (playthroughId, { snapshot_id, owner_id, location_id } = {}) => {
      const params = new URLSearchParams()
      if (snapshot_id != null) params.set('snapshot_id', snapshot_id)
      if (owner_id != null) params.set('owner_id', owner_id)
      if (location_id != null) params.set('location_id', location_id)
      const q = params.toString() ? `?${params}` : ''
      return request('GET', `/api/locations/${playthroughId}/snapshots${q}`)
    },

    /** GET /api/provinces/:id/snapshots?snapshot_id=&province_id= */
    getProvinceSnapshots: (playthroughId, { snapshot_id, province_id } = {}) => {
      const params = new URLSearchParams()
      if (snapshot_id != null) params.set('snapshot_id', snapshot_id)
      if (province_id != null) params.set('province_id', province_id)
      const q = params.toString() ? `?${params}` : ''
      return request('GET', `/api/provinces/${playthroughId}/snapshots${q}`)
    },

    // ── Demographics ────────────────────────────────────────────
    /** GET /api/pops/:id/snapshots?location_id=&snapshot_id=&pop_type=&limit= */
    getPopSnapshots: (playthroughId, { location_id, snapshot_id, pop_type, limit } = {}) => {
      const params = new URLSearchParams()
      if (location_id != null) params.set('location_id', location_id)
      if (snapshot_id != null) params.set('snapshot_id', snapshot_id)
      if (pop_type) params.set('pop_type', pop_type)
      if (limit) params.set('limit', limit)
      const q = params.toString() ? `?${params}` : ''
      return request('GET', `/api/pops/${playthroughId}/snapshots${q}`)
    },

    /** GET /api/pops/:id/aggregates?group_by=&snapshot_id=&owner_id= */
    getPopAggregates: (playthroughId, { group_by, snapshot_id, owner_id } = {}) => {
      const params = new URLSearchParams()
      if (group_by) params.set('group_by', group_by)
      if (snapshot_id != null) params.set('snapshot_id', snapshot_id)
      if (owner_id != null) params.set('owner_id', owner_id)
      const q = params.toString() ? `?${params}` : ''
      return request('GET', `/api/pops/${playthroughId}/aggregates${q}`)
    },
  }
}

/**
 * useApi — thin wrapper around fetch for the PDX backend REST API.
 *
 * All GET requests automatically receive an AbortSignal from AbortContext so
 * the user can cancel in-flight requests via the global abort button.
 * POST/PATCH control actions are never aborted (they mutate server state).
 */

import { useContext } from 'react'
import { AbortContext } from '../contexts/AbortContext'

const BASE = ''  // proxied through Vite dev server

async function request(method, path, body = null, signal = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (signal) opts.signal = signal
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
  const abortCtx = useContext(AbortContext)

  /**
   * Wraps a GET request with abort tracking.
   * Increments activeCount before the request, decrements on completion.
   */
  const get = (path) => {
    const signal = abortCtx?.getSignal() ?? null
    if (abortCtx) abortCtx.incrementActive()
    return request('GET', path, null, signal).finally(() => {
      if (abortCtx) abortCtx.decrementActive()
    })
  }

  return {
    /** GET /api/status */
    getStatus: () => get('/api/status'),

    /** POST /api/start — launch watcher pipeline */
    start: (config) => request('POST', '/api/start', config),

    /** POST /api/stop — stop watcher pipeline */
    stop: () => request('POST', '/api/stop'),

    /** GET /api/fields?category= */
    getFields: (category = null) => {
      const q = category ? `?category=${encodeURIComponent(category)}` : ''
      return get(`/api/fields${q}`)
    },

    /** GET /api/playthroughs?game= */
    getPlaythroughs: (game = null) => {
      const q = game ? `?game=${encodeURIComponent(game)}` : ''
      return get(`/api/playthroughs${q}`)
    },

    /** GET /api/snapshots/:id?limit=&after= */
    getSnapshots: (playthroughId, { limit, after } = {}) => {
      const params = new URLSearchParams()
      if (limit) params.set('limit', limit)
      if (after) params.set('after', after)
      const q = params.toString() ? `?${params}` : ''
      return get(`/api/snapshots/${playthroughId}${q}`)
    },

    /** GET /api/events/:id?event_type=&country_tag=&include_global=&limit= */
    getEvents: (playthroughId, { event_type, country_tags, include_global, limit } = {}) => {
      const params = new URLSearchParams()
      if (event_type) params.set('event_type', event_type)
      if (country_tags && country_tags.length > 0) {
        country_tags.forEach((t) => params.append('country_tag', t))
      }
      if (include_global === false) params.set('include_global', 'false')
      if (limit) params.set('limit', limit)
      const q = params.toString() ? `?${params}` : ''
      return get(`/api/events/${playthroughId}${q}`)
    },

    /** GET /api/events/:id/country-tags */
    getEventCountryTags: (playthroughId) =>
      get(`/api/events/${playthroughId}/country-tags`),

    /** PATCH /api/events/:id/note — set or update AAR note */
    updateAarNote: (eventId, note) =>
      request('PATCH', `/api/events/${eventId}/note`, { note }),

    /** GET /api/config?game= — load persisted config */
    getConfig: (game = 'eu5') => get(`/api/config?game=${encodeURIComponent(game)}`),

    /** POST /api/config — save config without starting pipeline */
    saveConfig: (config) => request('POST', '/api/config', config),

    /** POST /api/load-playthrough — open DB for browsing */
    loadPlaythrough: (game, playthroughId) =>
      request('POST', '/api/load-playthrough', { game, playthrough_id: playthroughId }),

    /** GET /api/scan-saves?save_directory=&game= — discover playthroughs from .eu5 files */
    scanSaves: (saveDirectory, game = 'eu5') => {
      const params = new URLSearchParams()
      params.set('save_directory', saveDirectory)
      params.set('game', game)
      return get(`/api/scan-saves?${params}`)
    },

    /** POST /api/playthroughs/:id/backfill — import historical saves */
    startBackfill: (playthroughId, { save_directory, game_install_path, language, game } = {}) =>
      request('POST', `/api/playthroughs/${playthroughId}/backfill`, {
        save_directory, game_install_path, language, game,
      }),

    // ── Religions ───────────────────────────────────────────────
    /** GET /api/religions/:id — static religion records */
    getReligions: (playthroughId) => get(`/api/religions/${playthroughId}`),

    // ── Cultures ────────────────────────────────────────────────
    /** GET /api/cultures/:id — static culture records */
    getCultures: (playthroughId) => get(`/api/cultures/${playthroughId}`),

    // ── Geography ───────────────────────────────────────────────
    /** GET /api/geography/:id — display names for all geo slugs in a playthrough */
    getGeography: (playthroughId) => get(`/api/geography/${playthroughId}`),

    /** GET /api/religions/:id/snapshots?religion_id= */
    getReligionSnapshots: (playthroughId, { religion_id } = {}) => {
      const params = new URLSearchParams()
      if (religion_id != null) params.set('religion_id', religion_id)
      const q = params.toString() ? `?${params}` : ''
      return get(`/api/religions/${playthroughId}/snapshots${q}`)
    },

    // ── Wars ────────────────────────────────────────────────────
    /** GET /api/wars/:id?active_only= */
    getWars: (playthroughId, { active_only } = {}) => {
      const params = new URLSearchParams()
      if (active_only) params.set('active_only', 'true')
      const q = params.toString() ? `?${params}` : ''
      return get(`/api/wars/${playthroughId}${q}`)
    },

    /** GET /api/wars/:id/snapshots?war_id= */
    getWarSnapshots: (playthroughId, { war_id } = {}) => {
      const params = new URLSearchParams()
      if (war_id) params.set('war_id', war_id)
      const q = params.toString() ? `?${params}` : ''
      return get(`/api/wars/${playthroughId}/snapshots${q}`)
    },

    /** GET /api/wars/:id/participants?war_id= */
    getWarParticipants: (playthroughId, { war_id } = {}) => {
      const params = new URLSearchParams()
      if (war_id) params.set('war_id', war_id)
      const q = params.toString() ? `?${params}` : ''
      return get(`/api/wars/${playthroughId}/participants${q}`)
    },

    // ── Geography ───────────────────────────────────────────────
    /** GET /api/locations/:id/snapshots?snapshot_id=&owner_id=&location_id= */
    getLocationSnapshots: (playthroughId, { snapshot_id, owner_id, location_id } = {}) => {
      const params = new URLSearchParams()
      if (snapshot_id != null) params.set('snapshot_id', snapshot_id)
      if (owner_id != null) params.set('owner_id', owner_id)
      if (location_id != null) params.set('location_id', location_id)
      const q = params.toString() ? `?${params}` : ''
      return get(`/api/locations/${playthroughId}/snapshots${q}`)
    },

    /** GET /api/provinces/:id/snapshots?snapshot_id=&province_id= */
    getProvinceSnapshots: (playthroughId, { snapshot_id, province_id } = {}) => {
      const params = new URLSearchParams()
      if (snapshot_id != null) params.set('snapshot_id', snapshot_id)
      if (province_id != null) params.set('province_id', province_id)
      const q = params.toString() ? `?${params}` : ''
      return get(`/api/provinces/${playthroughId}/snapshots${q}`)
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
      return get(`/api/pops/${playthroughId}/snapshots${q}`)
    },

    /**
     * GET /api/pops/:id/aggregates
     *   group_by:    "type" | "culture_id" | "religion_id" | "status" | "estate"
     *   from_date:   EU5 game date lower bound e.g. "1444.11.11"
     *   to_date:     EU5 game date upper bound (defaults to from_date on backend)
     *   owner_tags:  array of country TAGs to filter by (include predecessors for succession)
     */
    getPopAggregates: (playthroughId, { group_by, from_date, to_date, owner_tags } = {}) => {
      const params = new URLSearchParams()
      if (group_by) params.set('group_by', group_by)
      if (from_date) params.set('from_date', from_date)
      if (to_date) params.set('to_date', to_date)
      if (owner_tags && owner_tags.length > 0) {
        owner_tags.forEach((t) => params.append('owner_tags', t))
      }
      const q = params.toString() ? `?${params}` : ''
      return get(`/api/pops/${playthroughId}/aggregates${q}`)
    },

    /** GET /api/pops/:id/country-owners — distinct countries owning locations */
    getPopCountryOwners: (playthroughId) =>
      get(`/api/pops/${playthroughId}/country-owners`),

    /** GET /api/countries/:id — country reference table with succession data */
    getCountries: (playthroughId) =>
      get(`/api/countries/${playthroughId}`),

    // ── Military / Battles / Sieges ─────────────────────────────
    /** GET /api/military/:id?country_tags=&from_date=&to_date= */
    getMilitarySnapshots: (playthroughId, { country_tags, from_date, to_date } = {}) => {
      const params = new URLSearchParams()
      if (country_tags) params.set('country_tags', country_tags)
      if (from_date) params.set('from_date', from_date)
      if (to_date) params.set('to_date', to_date)
      const q = params.toString() ? `?${params}` : ''
      return get(`/api/military/${playthroughId}${q}`)
    },

    /** GET /api/battles/:id?war_id=&from_date=&to_date= */
    getBattles: (playthroughId, { war_id, from_date, to_date } = {}) => {
      const params = new URLSearchParams()
      if (war_id) params.set('war_id', war_id)
      if (from_date) params.set('from_date', from_date)
      if (to_date) params.set('to_date', to_date)
      const q = params.toString() ? `?${params}` : ''
      return get(`/api/battles/${playthroughId}${q}`)
    },

    /** GET /api/sieges/:id?war_id=&active_only= */
    getSieges: (playthroughId, { war_id, active_only } = {}) => {
      const params = new URLSearchParams()
      if (war_id) params.set('war_id', war_id)
      if (active_only) params.set('active_only', 'true')
      const q = params.toString() ? `?${params}` : ''
      return get(`/api/sieges/${playthroughId}${q}`)
    },

    /** GET /api/wars/:id/participant-history?war_id=&country_tags= */
    getWarParticipantHistory: (playthroughId, { war_id, country_tags } = {}) => {
      const params = new URLSearchParams()
      if (war_id) params.set('war_id', war_id)
      if (country_tags) params.set('country_tags', country_tags)
      const q = params.toString() ? `?${params}` : ''
      return get(`/api/wars/${playthroughId}/participant-history${q}`)
    },
  }
}

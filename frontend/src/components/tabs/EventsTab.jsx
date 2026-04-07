import { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import EventCard from '../EventCard'
import { useCountryNames } from '../../contexts/CountryNamesContext'
import { fmtCountry } from '../../utils/formatters'
import { usePerfTracker } from '../../hooks/usePerfTracker'
import { useApi } from '../../hooks/useApi'

const EVENT_TYPES = [
  'all',
  'age_transition',
  'ruler_changed',
  'war_started',
  'war_ended',
  'country_appeared',
  'country_annexed',
  'culture_changed',
  'religion_changed',
  'great_power_rank_changed',
  'situation_started',
  'situation_ended',
]

/**
 * EventsTab — self-contained: loads country tags first, then fetches events
 * only for the selected countries. Merges with live WS events.
 *
 * Props:
 *   playthroughId  — current playthrough UUID (from App.jsx status)
 *   liveEvents     — events pushed via WebSocket (from App.jsx)
 *   status         — current pipeline status (used to seed player tag)
 */
export default function EventsTab({ playthroughId, liveEvents = [], status }) {
  const api = useApi()
  const { track } = usePerfTracker('events')
  const nameMap = useCountryNames()

  // ── Available tags (loaded from DB cheaply on mount) ───────────────────
  const [availableTags, setAvailableTags] = useState([])
  const [tagsLoading, setTagsLoading] = useState(false)

  // ── Tag selection (drives the DB query) ───────────────────────────────
  const [selectedTags, setSelectedTags] = useState(new Set())

  // ── Loaded historical events ───────────────────────────────────────────
  const [historicalEvents, setHistoricalEvents] = useState([])
  const [eventsLoading, setEventsLoading] = useState(false)
  const [eventsError, setEventsError] = useState(null)
  // tracks what selection was last queried — null means "never loaded"
  const [loadedForTags, setLoadedForTags] = useState(null)

  // ── Display filters (client-side only, no re-fetch needed) ────────────
  const [typeFilter, setTypeFilter] = useState('all')
  const [includeGlobal, setIncludeGlobal] = useState(true)

  // ─────────────────────────────────────────────────────────────────────
  // Load available tags whenever playthroughId changes
  // ─────────────────────────────────────────────────────────────────────
  const prevPtId = useRef(null)
  const autoLoadedFor = useRef(null)

  useEffect(() => {
    if (!playthroughId || playthroughId === prevPtId.current) return
    prevPtId.current = playthroughId

    // Reset all state for new playthrough
    setAvailableTags([])
    setHistoricalEvents([])
    setLoadedForTags(null)
    setSelectedTags(new Set())
    setEventsError(null)
    setTagsLoading(true)

    api.getEventCountryTags(playthroughId)
      .then((tags) => {
        const list = tags || []
        setAvailableTags(list)

        // Pre-select player's country tag if present
        const playerTag = status?.country_tag
        if (playerTag && list.includes(playerTag)) {
          setSelectedTags(new Set([playerTag]))
        }
      })
      .catch(() => {})
      .finally(() => setTagsLoading(false))
  }, [playthroughId])  // eslint-disable-line react-hooks/exhaustive-deps

  // ─────────────────────────────────────────────────────────────────────
  // Auto-load once we have tags and a known player tag
  // ─────────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!playthroughId) return
    if (autoLoadedFor.current === playthroughId) return  // already done
    if (availableTags.length === 0) return

    const playerTag = status?.country_tag
    if (!playerTag || !availableTags.includes(playerTag)) return

    autoLoadedFor.current = playthroughId
    const initTags = new Set([playerTag])
    doFetchEvents(playthroughId, initTags)
  }, [playthroughId, availableTags, status?.country_tag])  // eslint-disable-line react-hooks/exhaustive-deps

  // ─────────────────────────────────────────────────────────────────────
  // Core fetch (called by auto-load and manual Load button)
  // ─────────────────────────────────────────────────────────────────────
  const doFetchEvents = useCallback(async (ptId, tags) => {
    setEventsError(null)
    setEventsLoading(true)
    try {
      const raw = await track(
        tags.size > 0 ? `events [${[...tags].join(', ')}]` : 'events [all]',
        api.getEvents(ptId, {
          country_tags: tags.size > 0 ? [...tags] : undefined,
          // always load global events (age transitions, situations, wars)
          // include_global defaults to true on the backend
        }),
      )
      const parsed = (raw || []).map((e) => ({
        ...e,
        payload: typeof e.payload === 'string' ? JSON.parse(e.payload) : e.payload,
      }))
      setHistoricalEvents(parsed)
      setLoadedForTags(new Set(tags))
    } catch (e) {
      setEventsError(e.message)
    } finally {
      setEventsLoading(false)
    }
  }, [api, track])

  const handleLoad = useCallback(() => {
    if (!playthroughId) return
    doFetchEvents(playthroughId, selectedTags)
  }, [playthroughId, selectedTags, doFetchEvents])

  // ── Tag toggle helpers ─────────────────────────────────────────────────
  const toggleTag = useCallback((tag) => {
    setSelectedTags((prev) => {
      const next = new Set(prev)
      if (next.has(tag)) next.delete(tag)
      else next.add(tag)
      return next
    })
  }, [])

  const selectAll = useCallback(() => setSelectedTags(new Set(availableTags)), [availableTags])
  const clearTags = useCallback(() => setSelectedTags(new Set()), [])

  // ── Handle note update locally ─────────────────────────────────────────
  const handleNoteUpdated = useCallback((eventId, noteText) => {
    setHistoricalEvents((prev) =>
      prev.map((e) => (e.id === eventId ? { ...e, aar_note: noteText } : e))
    )
  }, [])

  // ── Merge historical + live events ─────────────────────────────────────
  const allEvents = useMemo(() => {
    if (liveEvents.length === 0) return historicalEvents
    const historicalKeys = new Set(
      historicalEvents.map((e) => `${e.game_date}|${e.event_type}`)
    )
    const newLive = liveEvents.filter(
      (e) => !historicalKeys.has(`${e.game_date}|${e.event_type}`)
    )
    return [...historicalEvents, ...newLive]
  }, [historicalEvents, liveEvents])

  // ── Client-side display filters ────────────────────────────────────────
  const filtered = useMemo(() => {
    let list = allEvents

    // 1. Type filter
    if (typeFilter !== 'all') {
      list = list.filter((e) => e.event_type === typeFilter)
    }

    // 2. Global events toggle (client-side — no re-fetch needed)
    if (!includeGlobal) {
      list = list.filter((e) => {
        if (!e.country_tag) {
          // For wars, still show if participants include a loaded country
          if (e.event_type === 'war_started' || e.event_type === 'war_ended') {
            const participants = e.payload?.participants ?? []
            return loadedForTags ? participants.some((t) => loadedForTags.has(t)) : false
          }
          return false
        }
        return true
      })
    }

    return [...list].reverse()
  }, [allEvents, typeFilter, includeGlobal, loadedForTags])

  // ── Has the selection changed from what was last loaded? ──────────────
  const selectionChanged = loadedForTags !== null && (
    selectedTags.size !== loadedForTags.size ||
    [...selectedTags].some((t) => !loadedForTags.has(t))
  )

  const canLoad = !eventsLoading && !tagsLoading && playthroughId

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <div className="p-6 space-y-4">

      {/* ── Country tag picker ─────────────────────────────────────────── */}
      <div className="rounded-lg p-4" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
        <div className="flex items-center justify-between mb-2">
          <label className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
            {tagsLoading
              ? 'Loading countries…'
              : availableTags.length === 0
                ? 'No country events found'
                : `Countries (${selectedTags.size} / ${availableTags.length} selected)`}
          </label>
          <div className="flex items-center gap-2">
            {availableTags.length > 0 && !tagsLoading && (
              <>
                <button
                  onClick={selectAll}
                  className="text-xs px-2 py-0.5 rounded"
                  style={{ background: 'var(--color-surface-alt)', color: 'var(--color-text-muted)' }}
                >
                  All
                </button>
                <button
                  onClick={clearTags}
                  className="text-xs px-2 py-0.5 rounded"
                  style={{ background: 'var(--color-surface-alt)', color: 'var(--color-text-muted)' }}
                >
                  None
                </button>
              </>
            )}
            <button
              onClick={handleLoad}
              disabled={!canLoad}
              className="text-xs px-3 py-1 rounded font-medium"
              style={{
                background: selectionChanged
                  ? 'var(--color-warning, #f59e0b)'
                  : canLoad
                    ? 'var(--color-accent)'
                    : 'var(--color-surface-alt)',
                color: canLoad ? '#fff' : 'var(--color-text-muted)',
                cursor: canLoad ? 'pointer' : 'not-allowed',
                transition: 'background 0.15s',
              }}
            >
              {eventsLoading ? 'Loading…' : selectionChanged ? 'Refresh ↺' : loadedForTags === null ? 'Load Events' : 'Loaded ✓'}
            </button>
          </div>
        </div>

        {/* Tag pills */}
        {availableTags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {availableTags.map((tag) => {
              const active = selectedTags.has(tag)
              const isLoaded = loadedForTags?.has(tag)
              return (
                <button
                  key={tag}
                  onClick={() => toggleTag(tag)}
                  className="px-2 py-1 text-xs rounded transition-colors"
                  title={isLoaded && !active ? 'Loaded but deselected — hit Refresh to update' : undefined}
                  style={{
                    background: active ? 'var(--color-accent)' : 'var(--color-surface-alt)',
                    color: active ? '#fff' : 'var(--color-text-muted)',
                    outline: isLoaded && !active ? '1px dashed var(--color-border)' : 'none',
                  }}
                >
                  {fmtCountry(tag, nameMap)}
                </button>
              )
            })}
          </div>
        )}

        {/* Include global events toggle (client-side) */}
        {loadedForTags !== null && loadedForTags.size > 0 && (
          <label
            className="flex items-center gap-2 mt-2 text-xs cursor-pointer select-none"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <input
              type="checkbox"
              checked={includeGlobal}
              onChange={(e) => setIncludeGlobal(e.target.checked)}
              className="w-3.5 h-3.5 accent-[var(--color-accent)]"
            />
            Include global events (age transitions, situations, wars)
          </label>
        )}

        {/* Error */}
        {eventsError && (
          <div className="mt-2 text-xs rounded p-2" style={{ background: 'rgba(239,68,68,0.15)', color: 'var(--color-danger)' }}>
            {eventsError}
          </div>
        )}
      </div>

      {/* ── Type filter pills — only after events are loaded ──────────── */}
      {loadedForTags !== null && (
        <div>
          <label className="block text-xs mb-2" style={{ color: 'var(--color-text-muted)' }}>
            Filter by type
          </label>
          <div className="flex flex-wrap gap-1">
            {EVENT_TYPES.map((type) => {
              const count = type === 'all'
                ? allEvents.length
                : allEvents.filter((e) => e.event_type === type).length
              return (
                <button
                  key={type}
                  onClick={() => setTypeFilter(type)}
                  className="px-2 py-1 text-xs rounded capitalize transition-colors"
                  style={{
                    background: typeFilter === type ? 'var(--color-accent)' : 'var(--color-surface)',
                    color: typeFilter === type ? '#fff' : 'var(--color-text-muted)',
                  }}
                >
                  {type.replace(/_/g, ' ')} ({count})
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Loading skeleton ───────────────────────────────────────────── */}
      {eventsLoading && (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div
              key={i}
              className="h-16 rounded-lg animate-pulse"
              style={{ background: 'var(--color-surface)', opacity: 0.7 - i * 0.12 }}
            />
          ))}
        </div>
      )}

      {/* ── Event feed ─────────────────────────────────────────────────── */}
      {!eventsLoading && loadedForTags !== null && (
        filtered.length > 0 ? (
          <div className="space-y-2">
            {filtered.map((evt, i) => (
              <EventCard
                key={evt.id ?? `${evt.game_date}-${evt.event_type}-${i}`}
                event={evt}
                onNoteUpdated={handleNoteUpdated}
              />
            ))}
          </div>
        ) : (
          <div
            className="rounded-lg p-8 text-center text-sm"
            style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}
          >
            {allEvents.length === 0
              ? selectedTags.size === 0
                ? 'Select one or more countries above and click Load Events.'
                : 'No events found for the selected countries.'
              : `No events of type "${typeFilter.replace(/_/g, ' ')}".`}
          </div>
        )
      )}

      {/* ── Prompt when nothing loaded yet and not loading ────────────── */}
      {!eventsLoading && loadedForTags === null && !tagsLoading && availableTags.length > 0 && (
        <div
          className="rounded-lg p-8 text-center text-sm"
          style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}
        >
          Select countries above and click <strong>Load Events</strong>.
        </div>
      )}

    </div>
  )
}

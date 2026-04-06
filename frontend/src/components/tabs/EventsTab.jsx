import { useState, useMemo, useCallback } from 'react'
import EventCard from '../EventCard'
import { useCountryNames } from '../../contexts/CountryNamesContext'
import { fmtCountry } from '../../utils/formatters'
import { usePerfTracker } from '../../hooks/usePerfTracker'

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
 * EventsTab — receives merged historical + live events from App.jsx.
 *
 * Filters:
 *   - Event type (single-select pills, top row)
 *   - Country tags (multi-select toggle pills, second row)
 *   - Include global events checkbox (age transitions, situations, wars when a
 *     country filter is active)
 */
export default function EventsTab({ events: allEvents, onEventNoteUpdated }) {
  usePerfTracker('events')  // registers tab activation; data comes from App.jsx props

  // ── Event-type filter (single-select) ──────────────────────────────────
  const [typeFilter, setTypeFilter] = useState('all')

  // ── Country filter (multi-select) ──────────────────────────────────────
  const [selectedTags, setSelectedTags] = useState(new Set())
  const [includeGlobal, setIncludeGlobal] = useState(true)

  // Derive available tags from the loaded events (no extra API call needed)
  const availableTags = useMemo(() => {
    const tags = new Set()
    allEvents.forEach((e) => { if (e.country_tag) tags.add(e.country_tag) })
    return [...tags].sort()
  }, [allEvents])

  const toggleTag = useCallback((tag) => {
    setSelectedTags((prev) => {
      const next = new Set(prev)
      if (next.has(tag)) next.delete(tag)
      else next.add(tag)
      return next
    })
  }, [])

  const clearTags = useCallback(() => setSelectedTags(new Set()), [])

  // ── Filtered event list ─────────────────────────────────────────────────
  const filtered = useMemo(() => {
    let list = allEvents

    // 1. Type filter
    if (typeFilter !== 'all') {
      list = list.filter((e) => e.event_type === typeFilter)
    }

    // 2. Country filter
    if (selectedTags.size > 0) {
      list = list.filter((e) => {
        if (!e.country_tag) {
          // Event has no country tag (global: age transitions, situations, wars)
          if (!includeGlobal) {
            // Even with global hidden, war events that have a matching participant are shown
            if (e.event_type === 'war_started' || e.event_type === 'war_ended') {
              const participants = e.payload?.participants ?? []
              return participants.some((t) => selectedTags.has(t))
            }
            return false
          }
          return true  // include_global=true → always show null-tagged events
        }
        return selectedTags.has(e.country_tag)
      })
    }

    return [...list].reverse()
  }, [allEvents, typeFilter, selectedTags, includeGlobal])

  // ── Callback when note saved ────────────────────────────────────────────
  const handleNoteUpdated = useCallback((eventId, noteText) => {
    if (onEventNoteUpdated) onEventNoteUpdated(eventId, noteText)
  }, [onEventNoteUpdated])

  const hasCountryFilter = selectedTags.size > 0
  const nameMap = useCountryNames()

  return (
    <div className="p-6 space-y-4">

      {/* ── Row 1: Event type pills (single-select) ───────────────────── */}
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

      {/* ── Row 2: Country tag pills (multi-select) ───────────────────── */}
      {availableTags.length > 0 && (
        <div>
          <div className="flex items-center gap-3 mb-2">
            <label className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              Filter by country
            </label>
            {hasCountryFilter && (
              <button
                onClick={clearTags}
                className="text-xs px-1.5 py-0.5 rounded transition-colors"
                style={{ color: 'var(--color-accent)', background: 'var(--color-surface)' }}
              >
                clear
              </button>
            )}
          </div>
          <div className="flex flex-wrap gap-1">
            {availableTags.map((tag) => {
              const active = selectedTags.has(tag)
              return (
                <button
                  key={tag}
                  onClick={() => toggleTag(tag)}
                  className="px-2 py-1 text-xs rounded transition-colors"
                  style={{
                    background: active ? 'var(--color-accent)' : 'var(--color-surface)',
                    color: active ? '#fff' : 'var(--color-text-muted)',
                    outline: active ? 'none' : '1px solid transparent',
                  }}
                >
                  {fmtCountry(tag, nameMap)}
                </button>
              )
            })}
          </div>

          {/* Include global events checkbox — only visible when a tag is selected */}
          {hasCountryFilter && (
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
        </div>
      )}

      {/* ── Event feed ─────────────────────────────────────────────────── */}
      {filtered.length > 0 ? (
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
            ? 'No events detected yet. Start the pipeline and play the game.'
            : hasCountryFilter
              ? `No events match the selected country filter${typeFilter !== 'all' ? ` and type "${typeFilter.replace(/_/g, ' ')}"` : ''}.`
              : `No events of type "${typeFilter.replace(/_/g, ' ')}".`}
        </div>
      )}
    </div>
  )
}

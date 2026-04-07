/**
 * GameLocalizationContext — resolves EU5 numeric IDs and string keys to
 * human-readable display names for cultures, religions, and estates.
 *
 * Shape provided to consumers:
 *   fmtCulture(id)   int  → "Danube Bavarian"  (falls back to "culture_1062")
 *   fmtReligion(id)  int  → "Catholic"         (falls back to "religion_12")
 *   fmtEstate(key)   str  → "Nobles"           (falls back to key with underscores removed)
 *   cultures         { id → name }
 *   religions        { id → name }
 *
 * The provider is mounted in App.jsx and receives the active playthroughId.
 * When the playthrough changes it re-fetches both maps.
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { useApi } from '../hooks/useApi'

// ─── Static estate name map ───────────────────────────────────────────────────
// Covers all estate string keys known from EU5 pop_snapshots.estate column.
// Any unknown key is cleaned up dynamically (strip _estate, capitalise words).

const ESTATE_NAMES = {
  nobles_estate:    'Nobles',
  clergy_estate:    'Clergy',
  burghers_estate:  'Burghers',
  peasants_estate:  'Peasants',
  tribal_estate:    'Tribal',
  cossacks_estate:  'Cossacks',
  dhimmi_estate:    'Dhimmi',
  jains_estate:     'Jains',
  maratha_estate:   'Maratha',
  eunuchs_estate:   'Eunuchs',
  vaisyas_estate:   'Vaisyas',
  janissaries_estate: 'Janissaries',
  // Pop type labels (used when groupBy = "type", estate field absent)
  nobles:    'Nobles',
  clergy:    'Clergy',
  burghers:  'Burghers',
  peasants:  'Peasants',
  laborers:  'Laborers',
  soldiers:  'Soldiers',
  tribesmen: 'Tribesmen',
  slaves:    'Slaves',
}

function cleanEstateKey(key) {
  // "nobles_estate" → "Nobles",  "some_unknown_key" → "Some Unknown Key"
  return (key || '')
    .replace(/_estate$/, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

// ─── Context ─────────────────────────────────────────────────────────────────

export const GameLocalizationContext = createContext(null)

export function useGameLocalization() {
  return useContext(GameLocalizationContext)
}

// ─── Provider ─────────────────────────────────────────────────────────────────

export function GameLocalizationProvider({ children, playthroughId }) {
  const api = useApi()

  const [cultures,  setCultures]  = useState({})   // id (number) → display name
  const [religions, setReligions] = useState({})   // id (number) → display name

  useEffect(() => {
    if (!playthroughId) {
      setCultures({})
      setReligions({})
      return
    }

    // Fetch cultures
    api.getCultures(playthroughId)
      .then((data) => {
        const map = {}
        ;(data || []).forEach((c) => {
          map[c.id] = c.name || c.definition || `culture_${c.id}`
        })
        setCultures(map)
      })
      .catch(() => setCultures({}))

    // Fetch religions
    api.getReligions(playthroughId)
      .then((data) => {
        const map = {}
        ;(data || []).forEach((r) => {
          map[r.id] = r.name || r.definition || `religion_${r.id}`
        })
        setReligions(map)
      })
      .catch(() => setReligions({}))
  }, [playthroughId]) // eslint-disable-line react-hooks/exhaustive-deps

  const fmtCulture = useCallback(
    (id) => {
      if (id == null) return '—'
      return cultures[id] ?? cultures[Number(id)] ?? `culture_${id}`
    },
    [cultures],
  )

  const fmtReligion = useCallback(
    (id) => {
      if (id == null) return '—'
      return religions[id] ?? religions[Number(id)] ?? `religion_${id}`
    },
    [religions],
  )

  const fmtEstate = useCallback(
    (key) => {
      if (!key) return '—'
      return ESTATE_NAMES[key] ?? cleanEstateKey(key)
    },
    [],
  )

  return (
    <GameLocalizationContext.Provider
      value={{ fmtCulture, fmtReligion, fmtEstate, cultures, religions }}
    >
      {children}
    </GameLocalizationContext.Provider>
  )
}

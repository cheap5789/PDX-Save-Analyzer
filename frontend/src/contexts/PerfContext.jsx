/**
 * PerfContext — tracks data-loading milestones across tab sessions.
 *
 * A "session" is one tab activation.  Each session contains one or more
 * "requests" (individual API calls), each progressing through stages:
 *   fetching → received → ready (or error)
 *
 * Format timing is recorded separately when a tab calls fmt() after the
 * fetch resolves — covering expensive useMemo / chart-series builds.
 */

import { createContext, useContext, useState, useCallback, useRef } from 'react'

export const PerfContext = createContext(null)

export function PerfProvider({ children }) {
  // sessions[0] is always the most recent
  const [sessions, setSessions] = useState([])

  // Maps tab name → current sessionId so requests know which session they belong to
  const sessionIdFor = useRef({})

  // ---------------------------------------------------------------------------
  // Session lifecycle
  // ---------------------------------------------------------------------------

  const tabActivated = useCallback((tab) => {
    const sessionId = `${tab}__${Date.now()}`
    sessionIdFor.current[tab] = sessionId
    setSessions((prev) => [
      {
        sessionId,
        tab,
        activatedAt: Date.now(),
        requests: [],
      },
      ...prev.slice(0, 29), // keep last 30 sessions
    ])
  }, [])

  // ---------------------------------------------------------------------------
  // Request lifecycle helpers (called by usePerfTracker)
  // ---------------------------------------------------------------------------

  const _updateRequest = useCallback((tab, label, patch) => {
    const sessionId = sessionIdFor.current[tab]
    if (!sessionId) return
    setSessions((prev) =>
      prev.map((s) => {
        if (s.sessionId !== sessionId) return s
        const existing = s.requests.find((r) => r.label === label)
        if (existing) {
          return {
            ...s,
            requests: s.requests.map((r) =>
              r.label === label ? { ...r, ...patch } : r
            ),
          }
        }
        // Create new request entry
        return {
          ...s,
          requests: [
            ...s.requests,
            {
              label,
              stage: 'fetching',
              fetchStartAt: Date.now(),
              fetchMs: null,
              formatMs: null,
              rowCount: null,
              error: null,
              ...patch,
            },
          ],
        }
      })
    )
  }, [])

  const fetchStarted = useCallback(
    (tab, label) => _updateRequest(tab, label, { stage: 'fetching', fetchStartAt: Date.now(), fetchMs: null, formatMs: null, rowCount: null, error: null }),
    [_updateRequest]
  )

  const fetchReceived = useCallback(
    (tab, label, rowCount, fetchMs) =>
      _updateRequest(tab, label, { stage: 'received', rowCount, fetchMs }),
    [_updateRequest]
  )

  const formatDone = useCallback(
    (tab, label, formatMs) =>
      _updateRequest(tab, label, { stage: 'ready', formatMs }),
    [_updateRequest]
  )

  const fetchError = useCallback(
    (tab, label, error) =>
      _updateRequest(tab, label, { stage: 'error', error }),
    [_updateRequest]
  )

  // Mark a request ready without a separate format step (raw data used directly)
  const fetchReady = useCallback(
    (tab, label) => _updateRequest(tab, label, { stage: 'ready' }),
    [_updateRequest]
  )

  const clear = useCallback(() => setSessions([]), [])

  return (
    <PerfContext.Provider
      value={{
        sessions,
        tabActivated,
        fetchStarted,
        fetchReceived,
        formatDone,
        fetchReady,
        fetchError,
        clear,
      }}
    >
      {children}
    </PerfContext.Provider>
  )
}

export function usePerfContext() {
  return useContext(PerfContext)
}

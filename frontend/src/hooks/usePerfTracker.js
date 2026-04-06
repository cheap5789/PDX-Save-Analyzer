/**
 * usePerfTracker(tabName)
 *
 * Hook used inside tab components to record loading milestones.
 *
 * Returns:
 *   track(label, promise) — wraps a fetch promise, records fetch timing + row count
 *   fmt(label, fn)        — wraps a synchronous compute function, records duration
 *
 * Usage:
 *   const { track, fmt } = usePerfTracker('wars')
 *
 *   // Fetch tracking:
 *   useEffect(() => {
 *     track('wars', api.getWars(id)).then(setWars)
 *   }, [id])
 *
 *   // Format tracking (inside useMemo):
 *   const chartSeries = useMemo(() =>
 *     fmt('chart_series', () => buildSeries(wars)), [wars])
 */

import { useEffect, useCallback } from 'react'
import { usePerfContext } from '../contexts/PerfContext'

export function usePerfTracker(tab) {
  const ctx = usePerfContext()

  // Record tab activation on mount (or when tab name changes)
  useEffect(() => {
    ctx?.tabActivated(tab)
  }, [tab]) // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * Wrap a fetch promise.  Returns the same promise (data unchanged) so it
   * can be chained normally.
   */
  const track = useCallback(
    (label, promise) => {
      if (!ctx) return promise
      ctx.fetchStarted(tab, label)
      const t0 = Date.now()
      return Promise.resolve(promise)
        .then((data) => {
          const rowCount = Array.isArray(data)
            ? data.length
            : data != null
            ? 1
            : 0
          ctx.fetchReceived(tab, label, rowCount, Date.now() - t0)
          return data
        })
        .catch((err) => {
          ctx.fetchError(tab, label, err?.message ?? String(err))
          throw err
        })
    },
    [tab, ctx]
  )

  /**
   * Wrap a synchronous compute / format function.
   * Records how long the function took and marks the request as ready.
   * Call this inside useMemo after a tracked fetch has resolved.
   */
  const fmt = useCallback(
    (label, fn) => {
      if (!ctx) return fn()
      const t0 = Date.now()
      const result = fn()
      ctx.formatDone(tab, label, Date.now() - t0)
      return result
    },
    [tab, ctx]
  )

  return { track, fmt }
}

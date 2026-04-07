import { createContext, useContext, useRef, useState, useCallback } from 'react'

/**
 * AbortContext — global request abort mechanism.
 *
 * Provides a shared AbortSignal for all GET requests.  When the user clicks
 * "Abort", all in-flight fetches are cancelled and a fresh controller is
 * created so subsequent requests work normally.
 *
 * Also tracks the count of active GET requests so the header can show a
 * spinner and enable/disable the abort button accordingly.
 */
export const AbortContext = createContext(null)

export function AbortProvider({ children }) {
  const controllerRef = useRef(new AbortController())
  const [activeCount, setActiveCount] = useState(0)

  /** Return the current signal — called at request time, not at render time. */
  const getSignal = useCallback(() => controllerRef.current.signal, [])

  /** Cancel all in-flight requests and reset the controller. */
  const abortAll = useCallback(() => {
    controllerRef.current.abort()
    controllerRef.current = new AbortController()
    setActiveCount(0)
  }, [])

  const incrementActive = useCallback(() => setActiveCount((v) => v + 1), [])
  const decrementActive = useCallback(() => setActiveCount((v) => Math.max(0, v - 1)), [])

  return (
    <AbortContext.Provider value={{ getSignal, abortAll, activeCount, incrementActive, decrementActive }}>
      {children}
    </AbortContext.Provider>
  )
}

export function useAbortContext() {
  return useContext(AbortContext)
}

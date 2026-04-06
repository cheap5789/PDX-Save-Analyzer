import { createContext, useContext } from 'react'

/**
 * CountryNamesContext — provides per-TAG metadata derived from snapshot data.
 *
 * Shape: { TAG: { name: "France", color: "#0068a6" } }
 *
 * `_name` and `_color` are embedded in country rows by the backend's snapshot.py.
 *
 * Consumed via `useCountryMeta()` anywhere in the component tree.
 */
export const CountryNamesContext = createContext({})

export function useCountryNames() {
  return useContext(CountryNamesContext)
}

/**
 * Convenience accessors built on top of the context map.
 */
export function useCountryMeta() {
  return useContext(CountryNamesContext)
}

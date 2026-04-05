import { createContext, useContext } from 'react'

/**
 * CountryNamesContext — provides a { TAG: "Display Name" } lookup map
 * built from snapshot data (the `_name` field embedded per-country row).
 *
 * Consumed via `useCountryNames()` anywhere in the component tree.
 */
export const CountryNamesContext = createContext({})

export function useCountryNames() {
  return useContext(CountryNamesContext)
}

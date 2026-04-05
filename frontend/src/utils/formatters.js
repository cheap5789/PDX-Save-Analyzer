/**
 * formatters.js — Shared value formatting utilities
 *
 * display_format values (from the field catalog / FieldDef):
 *   "x1000"   — raw save value × 1000, displayed as an integer with locale separators
 *               (manpower, sailors, population — all stored as floats where 1.0 = 1,000)
 *   "percent" — value already on a 0–100 (or −100–+100) scale, append %
 *   ""        — plain number, two decimal places
 */

/**
 * Format a field value for display in tables, tooltips, and stat cards.
 * Returns a string.
 */
export function fmtValue(value, displayFormat) {
  if (value === null || value === undefined || value === '') return '—'
  const n = typeof value === 'number' ? value : parseFloat(value)
  if (isNaN(n)) return String(value)

  switch (displayFormat) {
    case 'x1000': {
      const scaled = Math.round(n * 1000)
      return scaled.toLocaleString()
    }
    case 'percent':
      return n.toFixed(1) + '%'
    default:
      return n.toFixed(2)
  }
}

/**
 * Format a value for a chart Y-axis tick — same logic as fmtValue but
 * abbreviated for brevity (e.g. 1,500,000 → "1.5M").
 */
export function fmtAxisTick(value, displayFormat) {
  if (value === null || value === undefined) return ''
  const n = typeof value === 'number' ? value : parseFloat(value)
  if (isNaN(n)) return ''

  switch (displayFormat) {
    case 'x1000': {
      const scaled = n * 1000
      if (Math.abs(scaled) >= 1_000_000)
        return (scaled / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M'
      if (Math.abs(scaled) >= 1_000)
        return (scaled / 1_000).toFixed(1).replace(/\.0$/, '') + 'K'
      return Math.round(scaled).toString()
    }
    case 'percent':
      return n.toFixed(1) + '%'
    default:
      return n % 1 === 0 ? n.toString() : n.toFixed(1)
  }
}

/**
 * Convenience: apply fmtValue using a field definition object
 * (any object with a display_format property, e.g. a FieldDefResponse).
 */
export function fmtFieldValue(value, fieldDef) {
  return fmtValue(value, fieldDef?.display_format ?? '')
}

/**
 * Format a country tag with its localised name: "France (FRA)".
 * Falls back to just the raw tag when no name is available or the name equals the tag.
 *
 * @param {string} tag          - Raw country TAG (e.g. "FRA")
 * @param {Record<string,string>} nameMap - tag → display name lookup (from CountryNamesContext)
 * @returns {string}
 */
export function fmtCountry(tag, nameMap) {
  if (!tag) return ''
  const name = nameMap?.[tag]
  if (!name || name === tag) return tag
  return `${name} (${tag})`
}

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
 * For TAG-switched nations also appends the predecessor: "Switzerland (SWI, ex-BRN)".
 * Falls back to just the raw tag when no name is available or the name equals the tag.
 *
 * @param {string} tag     - Raw country TAG (e.g. "SWI")
 * @param {Record<string,{name?:string,color?:string,prevTags?:string[]}>} metaMap
 * @param {{ showPrev?: boolean }} opts  - showPrev defaults to true
 * @returns {string}
 */
export function fmtCountry(tag, metaMap, { showPrev = true } = {}) {
  if (!tag) return ''
  const meta  = metaMap?.[tag]
  const name  = meta?.name
  const prev  = showPrev && meta?.prevTags?.length ? meta.prevTags.join('+') : null
  const label = name && name !== tag ? `${name} (${tag})` : tag
  return prev ? `${label}, ex-${prev}` : label
}

/**
 * Return the save-defined CSS color for a country tag, or a fallback.
 *
 * @param {string} tag
 * @param {Record<string,{name?:string,color?:string}>} metaMap
 * @param {string} fallback - CSS color to use when no color is known
 * @returns {string}
 */
export function countryColor(tag, metaMap, fallback = '#6b7280') {
  return metaMap?.[tag]?.color ?? fallback
}

// ─── EU5 date ↔ numeric conversion (for proportional time axes) ──────────────

/**
 * Convert an EU5 game date string to a fractional year number.
 *
 * EU5 dates are "year.month.day" (or "year.month.day.subtick" — extra
 * tokens are ignored).  The result is a monotonically increasing float
 * suitable for a Recharts linear X axis so that the visual gap between
 * two data points is proportional to actual in-game time elapsed.
 *
 * Examples:
 *   "1346.1.1"     → 1346.000
 *   "1514.7.1"     → 1514.500
 *   "1482.4.15"    → 1482.272
 *   "1352.5.27.22" → 1352.363  (sub-tick token ignored)
 */
export function euDateToNum(dateStr) {
  const parts = (dateStr || '').split('.')
  const year  = parseInt(parts[0], 10) || 0
  const month = parseInt(parts[1], 10) || 1
  const day   = parseInt(parts[2], 10) || 1
  return year + (month - 1) / 12 + (day - 1) / 365
}

/**
 * Format a fractional year value (from euDateToNum) as an integer year
 * label for X axis ticks.  Adds a small epsilon before flooring to avoid
 * e.g. 1482.000 rendering as "1481" due to float precision.
 */
export function fmtYearTick(v) {
  return String(Math.floor(v + 0.001))
}

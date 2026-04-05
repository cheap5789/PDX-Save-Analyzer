import { useState } from 'react'
import { useCountryNames } from '../contexts/CountryNamesContext'
import { fmtCountry } from '../utils/formatters'

/**
 * CountryPicker — checkbox list of country tags.
 * Props:
 *   available  — array of tag strings (e.g. ["FRA", "ENG", "CAS"])
 *   selected   — array of currently selected tags
 *   onChange   — callback(newSelectedArray)
 *   maxSelect  — optional cap (default 8)
 */
export default function CountryPicker({ available = [], selected = [], onChange, maxSelect = 8 }) {
  const [search, setSearch] = useState('')
  const nameMap = useCountryNames()

  const filtered = available.filter((tag) => {
    const q = search.toLowerCase()
    return (
      tag.toLowerCase().includes(q) ||
      (nameMap[tag] || '').toLowerCase().includes(q)
    )
  })

  const toggle = (tag) => {
    if (selected.includes(tag)) {
      onChange(selected.filter((t) => t !== tag))
    } else if (selected.length < maxSelect) {
      onChange([...selected, tag])
    }
  }

  return (
    <div className="rounded-lg p-3" style={{ background: 'var(--color-surface)' }}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
          Countries ({selected.length}/{maxSelect})
        </span>
        <input
          type="text"
          placeholder="Filter..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ml-auto text-xs px-2 py-1 rounded"
          style={{
            background: 'var(--color-surface-alt)',
            color: 'var(--color-text)',
            border: '1px solid var(--color-border)',
            outline: 'none',
            width: '100px',
          }}
        />
      </div>
      <div className="flex flex-wrap gap-1 max-h-32 overflow-y-auto">
        {filtered.map((tag) => {
          const active = selected.includes(tag)
          return (
            <button
              key={tag}
              onClick={() => toggle(tag)}
              className="px-2 py-0.5 text-xs rounded transition-colors"
              style={{
                background: active ? 'var(--color-accent)' : 'var(--color-surface-alt)',
                color: active ? '#fff' : 'var(--color-text-muted)',
                border: `1px solid ${active ? 'var(--color-accent)' : 'var(--color-border)'}`,
              }}
            >
              {fmtCountry(tag, nameMap)}
            </button>
          )
        })}
        {filtered.length === 0 && (
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>No matches</span>
        )}
      </div>
    </div>
  )
}

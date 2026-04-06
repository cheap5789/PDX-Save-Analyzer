import { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import { useApi } from '../../hooks/useApi'
import CountryPicker from '../CountryPicker'
import { fmtValue, fmtAxisTick, fmtCountry, countryColor } from '../../utils/formatters'
import { useCountryNames } from '../../contexts/CountryNamesContext'
import { usePerfTracker } from '../../hooks/usePerfTracker'

// Fallback palette used when a country has no save-defined color
const FALLBACK_COLORS = [
  '#3b82f6', '#ef4444', '#22c55e', '#f59e0b',
  '#8b5cf6', '#ec4899', '#06b6d4', '#f97316',
]

const FIELD_CATEGORIES = [
  'economy', 'military', 'stability', 'diplomacy',
  'religion', 'score', 'demographics', 'technology',
]

export default function ChartsTab({ snapshots, selectedCountries, onSelectedCountriesChange }) {
  const api = useApi()
  const { track, fmt } = usePerfTracker('charts')
  const [fields, setFields] = useState([])
  const [selectedCategory, setSelectedCategory] = useState('economy')
  const [selectedField, setSelectedField] = useState(null)

  // Load field catalog
  useEffect(() => {
    track('fields', api.getFields()).then(setFields).catch(() => {})
  }, [])

  // Fields for current category
  const categoryFields = useMemo(
    () => fields.filter((f) => f.category === selectedCategory),
    [fields, selectedCategory]
  )

  // Auto-select first field in category
  useEffect(() => {
    if (categoryFields.length > 0 && !categoryFields.find((f) => f.key === selectedField)) {
      setSelectedField(categoryFields[0].key)
    }
  }, [categoryFields])

  // All country tags that appear across snapshots
  const availableCountries = useMemo(() => {
    const tagSet = new Set()
    snapshots.forEach((snap) => {
      Object.keys(snap.countries || {}).forEach((tag) => tagSet.add(tag))
    })
    return Array.from(tagSet).sort()
  }, [snapshots])

  const metaMap = useCountryNames()
  const currentFieldDef = fields.find((f) => f.key === selectedField)

  // Transform snapshots into Recharts data: [{ date, FRA: 123, ENG: 456 }, ...]
  // For TAG-switched countries (e.g. SWI from BRN), transparently fall back to the
  // previous TAG's data in snapshots that predate the formation.
  const chartData = useMemo(() => fmt('chart_data', () => {
    if (!selectedField || selectedCountries.length === 0) return []
    return snapshots.map((snap) => {
      const point = { date: snap.game_date || '' }
      selectedCountries.forEach((tag) => {
        let countryData = snap.countries?.[tag]
        // Fall back to predecessor tags when the current tag has no data yet
        if (!countryData) {
          const prevTags = metaMap[tag]?.prevTags || []
          for (const pt of prevTags) {
            if (snap.countries?.[pt]) { countryData = snap.countries[pt]; break }
          }
        }
        if (countryData && selectedField in countryData) {
          point[tag] = countryData[selectedField]
        }
      })
      return point
    })
  }), [snapshots, selectedField, selectedCountries, metaMap])

  // Find the snapshot date when each selected country first appears (= TAG-switch moment)
  const tagSwitchDates = useMemo(() => {
    const result = {}
    for (const tag of selectedCountries) {
      if (!(metaMap[tag]?.prevTags?.length)) continue
      const switchSnap = snapshots.find((s) => s.countries?.[tag])
      if (switchSnap) result[tag] = switchSnap.game_date
    }
    return result
  }, [snapshots, selectedCountries, metaMap])

  return (
    <div className="p-6 space-y-4">
      {/* Controls row */}
      <div className="flex flex-wrap gap-4 items-start">
        {/* Category selector */}
        <div>
          <label className="block text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Category</label>
          <div className="flex flex-wrap gap-1">
            {FIELD_CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className="px-2 py-1 text-xs rounded capitalize transition-colors"
                style={{
                  background: selectedCategory === cat ? 'var(--color-accent)' : 'var(--color-surface)',
                  color: selectedCategory === cat ? '#fff' : 'var(--color-text-muted)',
                }}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Field selector */}
        <div>
          <label className="block text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Field</label>
          <select
            value={selectedField || ''}
            onChange={(e) => setSelectedField(e.target.value)}
            className="px-3 py-1.5 rounded text-sm"
            style={{
              background: 'var(--color-surface-alt)',
              color: 'var(--color-text)',
              border: '1px solid var(--color-border)',
            }}
          >
            {categoryFields.map((f) => (
              <option key={f.key} value={f.key}>{f.display_name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Country picker */}
      <CountryPicker
        available={availableCountries}
        selected={selectedCountries}
        onChange={onSelectedCountriesChange}
      />

      {/* Chart */}
      {chartData.length > 0 ? (
        <div className="rounded-lg p-4" style={{ background: 'var(--color-surface)' }}>
          <h3 className="text-sm font-medium mb-3">
            {currentFieldDef?.display_name || selectedField}
          </h3>
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis
                dataKey="date"
                tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
                stroke="var(--color-border)"
              />
              <YAxis
                tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
                stroke="var(--color-border)"
                tickFormatter={(v) => fmtAxisTick(v, currentFieldDef?.display_format)}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--color-surface-alt)',
                  border: '1px solid var(--color-border)',
                  borderRadius: '6px',
                  color: 'var(--color-text)',
                  fontSize: '12px',
                }}
                formatter={(v, name) => [fmtValue(v, currentFieldDef?.display_format), name]}
              />
              <Legend
                wrapperStyle={{ fontSize: '12px', color: 'var(--color-text-muted)' }}
              />
              {selectedCountries.map((tag, i) => (
                <Line
                  key={tag}
                  type="monotone"
                  dataKey={tag}
                  name={fmtCountry(tag, metaMap, { showPrev: false })}
                  stroke={countryColor(tag, metaMap, FALLBACK_COLORS[i % FALLBACK_COLORS.length])}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              ))}
              {/* TAG-switch reference lines — one vertical marker per switch event */}
              {Object.entries(tagSwitchDates).map(([tag, date]) => {
                const prevLabel = (metaMap[tag]?.prevTags || []).join('+')
                const color = countryColor(tag, metaMap, '#6b7280')
                return (
                  <ReferenceLine
                    key={`switch-${tag}`}
                    x={date}
                    stroke={color}
                    strokeDasharray="4 3"
                    strokeOpacity={0.7}
                    label={{
                      value: `${prevLabel} → ${tag}`,
                      position: 'insideTopRight',
                      fontSize: 10,
                      fill: color,
                      offset: 4,
                    }}
                  />
                )
              })}
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div
          className="rounded-lg p-8 text-center text-sm"
          style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}
        >
          {snapshots.length === 0
            ? 'No snapshots yet. Start the pipeline and play the game.'
            : 'Select a field and at least one country to display a chart.'}
        </div>
      )}
    </div>
  )
}

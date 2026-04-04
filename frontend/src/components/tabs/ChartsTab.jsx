import { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { useApi } from '../../hooks/useApi'
import CountryPicker from '../CountryPicker'

// Distinct colors for up to 8 overlaid country lines
const LINE_COLORS = [
  '#3b82f6', '#ef4444', '#22c55e', '#f59e0b',
  '#8b5cf6', '#ec4899', '#06b6d4', '#f97316',
]

const FIELD_CATEGORIES = [
  'economy', 'military', 'stability', 'diplomacy',
  'religion', 'score', 'demographics', 'technology',
]

export default function ChartsTab({ snapshots, status }) {
  const api = useApi()
  const [fields, setFields] = useState([])
  const [selectedCategory, setSelectedCategory] = useState('economy')
  const [selectedField, setSelectedField] = useState(null)
  const [selectedCountries, setSelectedCountries] = useState([])

  // Load field catalog
  useEffect(() => {
    api.getFields().then(setFields).catch(() => {})
  }, [])

  // Auto-select player tag when status arrives
  useEffect(() => {
    if (status?.country_tag && selectedCountries.length === 0) {
      setSelectedCountries([status.country_tag])
    }
  }, [status?.country_tag])

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

  // Transform snapshots into Recharts data: [{ date, FRA: 123, ENG: 456 }, ...]
  const chartData = useMemo(() => {
    if (!selectedField || selectedCountries.length === 0) return []
    return snapshots.map((snap) => {
      const point = { date: snap.game_date || '' }
      selectedCountries.forEach((tag) => {
        const countryData = snap.countries?.[tag]
        if (countryData && selectedField in countryData) {
          point[tag] = countryData[selectedField]
        }
      })
      return point
    })
  }, [snapshots, selectedField, selectedCountries])

  const currentFieldDef = fields.find((f) => f.key === selectedField)

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
        onChange={setSelectedCountries}
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
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--color-surface-alt)',
                  border: '1px solid var(--color-border)',
                  borderRadius: '6px',
                  color: 'var(--color-text)',
                  fontSize: '12px',
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: '12px', color: 'var(--color-text-muted)' }}
              />
              {selectedCountries.map((tag, i) => (
                <Line
                  key={tag}
                  type="monotone"
                  dataKey={tag}
                  stroke={LINE_COLORS[i % LINE_COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              ))}
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

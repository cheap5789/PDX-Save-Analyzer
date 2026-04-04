import { useState, useEffect } from 'react'
import { useApi } from '../../hooks/useApi'

const FREQUENCIES = [
  { value: 'every_save', label: 'Every Save' },
  { value: 'yearly', label: 'Yearly' },
  { value: '5years', label: 'Every 5 Years' },
  { value: '10years', label: 'Every 10 Years' },
  { value: '25years', label: 'Every 25 Years' },
]

const FIELD_CATEGORIES = [
  'economy', 'military', 'stability', 'diplomacy',
  'religion', 'score', 'demographics', 'technology',
]

export default function ConfigTab({ status, onStatusChange }) {
  const api = useApi()
  const [config, setConfig] = useState({
    game: 'eu5',
    game_install_path: 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\Europa Universalis V',
    save_directory: '',
    snapshot_freq: 'yearly',
    language: 'english',
    enabled_field_keys: [],
  })
  const [fields, setFields] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  // Load field catalog on mount
  useEffect(() => {
    api.getFields()
      .then((data) => {
        setFields(data)
        // Pre-select default-enabled fields
        const defaults = data.filter((f) => f.default_enabled).map((f) => f.key)
        setConfig((prev) => ({ ...prev, enabled_field_keys: defaults }))
      })
      .catch(() => {/* fields endpoint may not be available yet */})
  }, [])

  const running = status?.running

  const handleStart = async () => {
    setError(null)
    setLoading(true)
    try {
      await api.start(config)
      const newStatus = await api.getStatus()
      onStatusChange(newStatus)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleStop = async () => {
    setError(null)
    setLoading(true)
    try {
      await api.stop()
      const newStatus = await api.getStatus()
      onStatusChange(newStatus)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const toggleField = (key) => {
    setConfig((prev) => {
      const keys = prev.enabled_field_keys.includes(key)
        ? prev.enabled_field_keys.filter((k) => k !== key)
        : [...prev.enabled_field_keys, key]
      return { ...prev, enabled_field_keys: keys }
    })
  }

  const inputStyle = {
    background: 'var(--color-surface-alt)',
    color: 'var(--color-text)',
    border: '1px solid var(--color-border)',
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <h2 className="text-lg font-semibold">Pipeline Configuration</h2>

      {/* Path inputs */}
      <div className="space-y-3">
        <div>
          <label className="block text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>
            Game Install Path
          </label>
          <input
            type="text"
            value={config.game_install_path}
            onChange={(e) => setConfig({ ...config, game_install_path: e.target.value })}
            disabled={running}
            className="w-full px-3 py-2 rounded text-sm"
            style={inputStyle}
          />
        </div>
        <div>
          <label className="block text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>
            Save Directory
          </label>
          <input
            type="text"
            value={config.save_directory}
            onChange={(e) => setConfig({ ...config, save_directory: e.target.value })}
            disabled={running}
            placeholder="e.g. C:\Users\YourName\Documents\Paradox Interactive\Europa Universalis V\save games"
            className="w-full px-3 py-2 rounded text-sm"
            style={inputStyle}
          />
        </div>
      </div>

      {/* Frequency + Language row */}
      <div className="flex gap-4">
        <div className="flex-1">
          <label className="block text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>
            Snapshot Frequency
          </label>
          <select
            value={config.snapshot_freq}
            onChange={(e) => setConfig({ ...config, snapshot_freq: e.target.value })}
            disabled={running}
            className="w-full px-3 py-2 rounded text-sm"
            style={inputStyle}
          >
            {FREQUENCIES.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
        </div>
        <div className="flex-1">
          <label className="block text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>
            Language
          </label>
          <input
            type="text"
            value={config.language}
            onChange={(e) => setConfig({ ...config, language: e.target.value })}
            disabled={running}
            className="w-full px-3 py-2 rounded text-sm"
            style={inputStyle}
          />
        </div>
      </div>

      {/* Field toggles */}
      <div>
        <label className="block text-xs mb-2" style={{ color: 'var(--color-text-muted)' }}>
          Tracked Fields ({config.enabled_field_keys.length} / {fields.length})
        </label>
        <div className="space-y-3">
          {FIELD_CATEGORIES.map((cat) => {
            const catFields = fields.filter((f) => f.category === cat)
            if (catFields.length === 0) return null
            return (
              <div key={cat}>
                <div className="text-xs font-medium capitalize mb-1" style={{ color: 'var(--color-accent)' }}>
                  {cat}
                </div>
                <div className="flex flex-wrap gap-1">
                  {catFields.map((f) => {
                    const active = config.enabled_field_keys.includes(f.key)
                    return (
                      <button
                        key={f.key}
                        onClick={() => !running && toggleField(f.key)}
                        disabled={running}
                        title={f.description || f.display_name}
                        className="px-2 py-0.5 text-xs rounded transition-colors"
                        style={{
                          background: active ? 'var(--color-accent)' : 'var(--color-surface-alt)',
                          color: active ? '#fff' : 'var(--color-text-muted)',
                          border: `1px solid ${active ? 'var(--color-accent)' : 'var(--color-border)'}`,
                          opacity: running ? 0.5 : 1,
                          cursor: running ? 'not-allowed' : 'pointer',
                        }}
                      >
                        {f.display_name}
                      </button>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Error display */}
      {error && (
        <div className="rounded p-3 text-sm" style={{ background: 'rgba(239,68,68,0.15)', color: 'var(--color-danger)' }}>
          {error}
        </div>
      )}

      {/* Start / Stop button */}
      <div className="flex gap-3">
        {!running ? (
          <button
            onClick={handleStart}
            disabled={loading || !config.save_directory}
            className="px-6 py-2 rounded font-medium text-sm text-white transition-colors"
            style={{
              background: loading ? 'var(--color-surface-alt)' : 'var(--color-accent)',
              cursor: loading || !config.save_directory ? 'not-allowed' : 'pointer',
              opacity: !config.save_directory ? 0.5 : 1,
            }}
          >
            {loading ? 'Starting...' : 'Start Pipeline'}
          </button>
        ) : (
          <button
            onClick={handleStop}
            disabled={loading}
            className="px-6 py-2 rounded font-medium text-sm text-white transition-colors"
            style={{
              background: loading ? 'var(--color-surface-alt)' : 'var(--color-danger)',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Stopping...' : 'Stop Pipeline'}
          </button>
        )}
      </div>
    </div>
  )
}

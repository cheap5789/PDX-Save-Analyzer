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

export default function ConfigTab({ status, onStatusChange, backfillProgress }) {
  const api = useApi()
  const game = 'eu5' // hardcoded for now — game-dependent

  const [config, setConfig] = useState({
    game,
    game_install_path: 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\Europa Universalis V',
    save_directory: '',
    snapshot_freq: 'yearly',
    language: 'english',
    enabled_field_keys: [],
    selected_playthrough_id: '',
  })
  const [fields, setFields] = useState([])
  const [playthroughs, setPlaythroughs] = useState([])
  // Initialize dropdown from current status (survives tab switch) or empty
  const [selectedPlaythrough, setSelectedPlaythrough] = useState(status?.playthrough_id || '')
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [loading, setLoading] = useState(false)

  // Backfill state
  const [backfillRunning, setBackfillRunning] = useState(false)
  const [backfillError, setBackfillError] = useState(null)

  // Load field catalog, saved config, and existing playthroughs on mount
  useEffect(() => {
    Promise.all([
      api.getFields().catch(() => []),
      api.getConfig(game).catch(() => null),
      api.getPlaythroughs(game).catch(() => []),
    ]).then(([fieldData, savedConfig, ptList]) => {
      setFields(fieldData)
      setPlaythroughs(ptList)

      if (savedConfig && savedConfig.game_install_path) {
        setConfig((prev) => ({
          ...prev,
          game: savedConfig.game || prev.game,
          game_install_path: savedConfig.game_install_path || prev.game_install_path,
          save_directory: savedConfig.save_directory || prev.save_directory,
          snapshot_freq: savedConfig.snapshot_freq || prev.snapshot_freq,
          language: savedConfig.language || prev.language,
          enabled_field_keys: savedConfig.enabled_field_keys.length > 0
            ? savedConfig.enabled_field_keys
            : fieldData.map((f) => f.key),
          selected_playthrough_id: savedConfig.selected_playthrough_id || '',
        }))
        // Restore the dropdown: prefer current status (active playthrough), then saved config
        const restoredPt = status?.playthrough_id || savedConfig.selected_playthrough_id || ''
        if (restoredPt) {
          setSelectedPlaythrough(restoredPt)
        }
      } else {
        // No saved config — all fields enabled by default
        setConfig((prev) => ({ ...prev, enabled_field_keys: fieldData.map((f) => f.key) }))
      }
    })
  }, [])

  const running = status?.running

  // --- Action handlers ---

  const handleSaveConfig = async () => {
    setError(null)
    setSuccess(null)
    try {
      await api.saveConfig(config)
      setSuccess('Config saved.')
      setTimeout(() => setSuccess(null), 3000)
    } catch (e) {
      setError(e.message)
    }
  }

  const handleStart = async () => {
    setError(null)
    setSuccess(null)
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
    setSuccess(null)
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

  const handleLoadPlaythrough = async () => {
    if (!selectedPlaythrough) return
    setError(null)
    setSuccess(null)
    setLoading(true)
    try {
      const result = await api.loadPlaythrough(game, selectedPlaythrough)
      // Persist the selected playthrough in config
      const updatedConfig = { ...config, selected_playthrough_id: selectedPlaythrough }
      setConfig(updatedConfig)
      await api.saveConfig(updatedConfig).catch(() => {})
      const newStatus = await api.getStatus()
      onStatusChange(newStatus)
      setSuccess(`Loaded playthrough: ${result.country_name || result.country_tag} (${result.snapshot_count} snapshots, ${result.event_count} events)`)
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

  const selectAll = () => setConfig((prev) => ({ ...prev, enabled_field_keys: fields.map((f) => f.key) }))
  const selectNone = () => setConfig((prev) => ({ ...prev, enabled_field_keys: [] }))

  // Watch for backfill completion via WS progress
  useEffect(() => {
    if (backfillProgress?.done) {
      setBackfillRunning(false)
    }
  }, [backfillProgress?.done])

  const handleBackfill = async () => {
    if (!status?.playthrough_id || !config.save_directory) return
    setBackfillError(null)
    setBackfillRunning(true)
    try {
      await api.startBackfill(status.playthrough_id, {
        save_directory: config.save_directory,
        game_install_path: config.game_install_path,
        language: config.language,
        game: config.game,
      })
      // Progress will arrive via WS backfillProgress prop
    } catch (e) {
      setBackfillError(e.message)
      setBackfillRunning(false)
    }
  }

  const inputStyle = {
    background: 'var(--color-surface-alt)',
    color: 'var(--color-text)',
    border: '1px solid var(--color-border)',
  }

  const btnBase = 'px-5 py-2 rounded font-medium text-sm transition-colors'

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold">EU5 Configuration</h2>
        {running && (
          <span className="text-xs px-2 py-0.5 rounded" style={{ background: 'rgba(34,197,94,0.2)', color: 'var(--color-success)' }}>
            Pipeline running
          </span>
        )}
      </div>

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
        <div className="flex items-center gap-3 mb-2">
          <label className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Tracked Fields ({config.enabled_field_keys.length} / {fields.length})
          </label>
          {!running && (
            <div className="flex gap-1">
              <button onClick={selectAll} className="text-xs px-2 py-0.5 rounded" style={{ background: 'var(--color-surface-alt)', color: 'var(--color-text-muted)' }}>All</button>
              <button onClick={selectNone} className="text-xs px-2 py-0.5 rounded" style={{ background: 'var(--color-surface-alt)', color: 'var(--color-text-muted)' }}>None</button>
            </div>
          )}
        </div>
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

      {/* Load existing playthrough section */}
      {playthroughs.length > 0 && !running && (
        <div className="rounded-lg p-4" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
          <label className="block text-xs mb-2" style={{ color: 'var(--color-text-muted)' }}>
            Load existing playthrough
          </label>
          <div className="flex gap-2">
            <select
              value={selectedPlaythrough}
              onChange={(e) => setSelectedPlaythrough(e.target.value)}
              className="flex-1 px-3 py-2 rounded text-sm"
              style={inputStyle}
            >
              <option value="">Select a playthrough...</option>
              {playthroughs.map((pt) => (
                <option key={pt.id} value={pt.id}>
                  {pt.country_name || pt.country_tag || 'Unknown'} — {pt.playthrough_name || pt.id.slice(0, 8)} ({pt.last_game_date || '?'})
                </option>
              ))}
            </select>
            <button
              onClick={handleLoadPlaythrough}
              disabled={!selectedPlaythrough || loading}
              className={btnBase + ' text-white'}
              style={{
                background: !selectedPlaythrough || loading ? 'var(--color-surface-alt)' : 'var(--color-accent)',
                cursor: !selectedPlaythrough || loading ? 'not-allowed' : 'pointer',
              }}
            >
              Load
            </button>
          </div>
        </div>
      )}

      {/* Import Historical Saves */}
      {status?.playthrough_id && (
        <div className="rounded-lg p-4" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
          <div className="flex items-center justify-between mb-2">
            <div>
              <div className="text-sm font-medium">Import Historical Saves</div>
              <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                Scan the save folder for existing saves belonging to this playthrough and add them to the database.
              </div>
            </div>
            <button
              onClick={handleBackfill}
              disabled={backfillRunning || !config.save_directory}
              className="ml-4 px-4 py-1.5 rounded text-sm font-medium text-white shrink-0"
              style={{
                background: backfillRunning || !config.save_directory
                  ? 'var(--color-surface-alt)'
                  : 'var(--color-accent)',
                color: backfillRunning || !config.save_directory ? 'var(--color-text-muted)' : '#fff',
                cursor: backfillRunning || !config.save_directory ? 'not-allowed' : 'pointer',
              }}
            >
              {backfillRunning ? 'Scanning…' : 'Start Import'}
            </button>
          </div>

          {/* Progress */}
          {(backfillRunning || backfillProgress) && (
            <div className="mt-3 space-y-2">
              {/* Progress bar */}
              {backfillProgress && backfillProgress.total > 0 && (
                <div className="w-full rounded-full h-1.5" style={{ background: 'var(--color-surface-alt)' }}>
                  <div
                    className="h-1.5 rounded-full transition-all"
                    style={{
                      background: backfillProgress.done ? 'var(--color-success)' : 'var(--color-accent)',
                      width: `${Math.round(((backfillProgress.processed || 0) / backfillProgress.total) * 100)}%`,
                    }}
                  />
                </div>
              )}

              {/* Current file */}
              {backfillProgress?.current_file && !backfillProgress.done && (
                <div className="text-xs truncate" style={{ color: 'var(--color-text-muted)' }}>
                  {backfillProgress.current_file}
                </div>
              )}

              {/* Stats row */}
              {backfillProgress && (
                <div className="flex gap-4 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  <span>{backfillProgress.processed ?? 0} / {backfillProgress.total ?? 0} files</span>
                  <span style={{ color: 'var(--color-success)' }}>{backfillProgress.added ?? 0} added</span>
                  <span>{backfillProgress.skipped ?? 0} already in DB</span>
                  {(backfillProgress.errors ?? 0) > 0 && (
                    <span style={{ color: 'var(--color-danger)' }}>{backfillProgress.errors} errors</span>
                  )}
                  {backfillProgress.done && (
                    <span style={{ color: 'var(--color-success)', fontWeight: 600 }}>Done</span>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Backfill error */}
          {backfillError && (
            <div className="mt-2 text-xs rounded p-2" style={{ background: 'rgba(239,68,68,0.15)', color: 'var(--color-danger)' }}>
              {backfillError}
            </div>
          )}
        </div>
      )}

      {/* Messages */}
      {error && (
        <div className="rounded p-3 text-sm" style={{ background: 'rgba(239,68,68,0.15)', color: 'var(--color-danger)' }}>
          {error}
        </div>
      )}
      {success && (
        <div className="rounded p-3 text-sm" style={{ background: 'rgba(34,197,94,0.15)', color: 'var(--color-success)' }}>
          {success}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-3 pt-2" style={{ borderTop: '1px solid var(--color-border)' }}>
        {/* Save Config — always available when not running */}
        {!running && (
          <button
            onClick={handleSaveConfig}
            disabled={loading}
            className={btnBase}
            style={{
              background: 'var(--color-surface-alt)',
              color: 'var(--color-text)',
              border: '1px solid var(--color-border)',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            Save Config
          </button>
        )}

        {/* Start Pipeline — only when not running */}
        {!running && (
          <button
            onClick={handleStart}
            disabled={loading || !config.save_directory}
            className={btnBase + ' text-white'}
            style={{
              background: loading || !config.save_directory ? 'var(--color-surface-alt)' : 'var(--color-success)',
              cursor: loading || !config.save_directory ? 'not-allowed' : 'pointer',
              opacity: !config.save_directory ? 0.5 : 1,
            }}
          >
            {loading ? 'Starting...' : 'Start Pipeline'}
          </button>
        )}

        {/* Stop Pipeline — only when running */}
        {running && (
          <button
            onClick={handleStop}
            disabled={loading}
            className={btnBase + ' text-white'}
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

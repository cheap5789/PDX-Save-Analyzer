import { useState, useEffect, useMemo } from 'react'
import { useApi } from '../../hooks/useApi'
import { usePerfTracker } from '../../hooks/usePerfTracker'
import { useGameLocalization } from '../../contexts/GameLocalizationContext.jsx'

const RANK_COLORS = {
  city: '#f59e0b',
  town: '#3b82f6',
  rural_settlement: '#6b7280',
}

const INTEGRATION_COLORS = {
  core: '#22c55e',
  integrated: '#3b82f6',
  conquered: '#ef4444',
  colonized: '#8b5cf6',
  none: '#6b7280',
}

// Geography column selector options — user-chosen hierarchy level shown in
// the table. Defaults to "region" (see docs/territory-tab.md discussion).
const GEO_LEVELS = [
  { key: 'area',      label: 'Area' },
  { key: 'region',    label: 'Region' },
  { key: 'continent', label: 'Continent' },
]

export default function TerritoryTab({ status }) {
  const api = useApi()
  const { track, fmt } = usePerfTracker('territory')
  const gameLoc = useGameLocalization()
  const [locationData, setLocationData] = useState([])
  const [sortField, setSortField] = useState('development')
  const [sortDir, setSortDir] = useState('desc')
  const [filterRank, setFilterRank] = useState('all')
  const [filterIntegration, setFilterIntegration] = useState('all')
  const [searchText, setSearchText] = useState('')
  const [geoLevel, setGeoLevel] = useState('region')  // area | region | continent
  const ptId = status?.playthrough_id

  // Load location data for the latest snapshot (all owned locations).
  // The backend already enriches each row with location_slug, area/region/
  // sub_continent/continent, and owner_name — via LEFT JOIN on locations
  // and countries (keyed by owner_id, not owner_tag; see
  // docs/games/eu5/duplicate-tags.md).
  useEffect(() => {
    if (!ptId) return
    let cancelled = false
    track('latest_snapshot', api.getSnapshots(ptId, { limit: 1 }).catch(() => [])).then((apiSnaps) => {
      if (cancelled || apiSnaps.length === 0) return
      const latestSnap = apiSnaps[apiSnaps.length - 1]
      return track('locations', api.getLocationSnapshots(ptId, { snapshot_id: latestSnap.id }))
    }).then((locs) => {
      if (!cancelled && locs) setLocationData(locs)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [ptId])

  // Helpers — resolve display strings for a snapshot row using the localisation
  // context. The backend already hands us the slug on each row, so these are
  // pure formatters.
  const fmtLocationCell = (loc) => {
    if (!gameLoc) return `${loc.location_id}`
    const name = gameLoc.fmtLocation(loc.location_slug) || `#${loc.location_id}`
    return `${name} (${loc.location_id})`
  }

  const fmtOwnerCell = (loc) => {
    if (!loc.owner_tag) return '—'
    return loc.owner_name ? `${loc.owner_name} (${loc.owner_tag})` : loc.owner_tag
  }

  const fmtGeoCell = (loc) => {
    if (!gameLoc) return loc[geoLevel] || '—'
    if (geoLevel === 'area')      return gameLoc.fmtArea(loc.area)
    if (geoLevel === 'region')    return gameLoc.fmtRegion(loc.region)
    if (geoLevel === 'continent') return gameLoc.fmtContinent(loc.continent)
    return loc[geoLevel] || '—'
  }

  // Aggregated stats
  const stats = useMemo(() => {
    const ranks = {}
    const integrations = {}
    let totalDev = 0
    let totalPops = 0

    locationData.forEach((loc) => {
      const r = loc.rank || 'unknown'
      ranks[r] = (ranks[r] || 0) + 1
      const i = loc.integration_type || 'none'
      integrations[i] = (integrations[i] || 0) + 1
      totalDev += loc.development || 0
      totalPops += loc.pop_count || 0
    })
    return { ranks, integrations, totalDev, totalPops, totalLocs: locationData.length }
  }, [locationData])

  // Filter + sort. Search matches across location name, owner name/tag,
  // and the currently-selected geography level (per user spec 2026-04-09).
  const displayData = useMemo(() => fmt('filter_sort', () => {
    let data = [...locationData]

    if (filterRank !== 'all') {
      data = data.filter((l) => l.rank === filterRank)
    }
    if (filterIntegration !== 'all') {
      data = data.filter((l) => (l.integration_type || 'none') === filterIntegration)
    }
    if (searchText) {
      const q = searchText.toLowerCase()
      data = data.filter((l) => {
        const locName  = (gameLoc?.fmtLocation(l.location_slug) || '').toLowerCase()
        const ownerStr = fmtOwnerCell(l).toLowerCase()
        const geoStr   = (fmtGeoCell(l) || '').toLowerCase()
        return (
          locName.includes(q) ||
          String(l.location_id).includes(q) ||
          ownerStr.includes(q) ||
          geoStr.includes(q) ||
          (l.language || '').toLowerCase().includes(q) ||
          (l.dialect || '').toLowerCase().includes(q)
        )
      })
    }

    data.sort((a, b) => {
      const av = a[sortField] ?? -Infinity
      const bv = b[sortField] ?? -Infinity
      return sortDir === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1)
    })

    return data
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [locationData, filterRank, filterIntegration, searchText, sortField, sortDir, geoLevel, gameLoc])

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDir('desc')
    }
  }

  const sortIcon = (field) => {
    if (sortField !== field) return ''
    return sortDir === 'asc' ? ' \u25B2' : ' \u25BC'
  }

  if (!ptId) {
    return (
      <div className="p-6 text-sm" style={{ color: 'var(--color-text-muted)' }}>
        No playthrough loaded. Start the pipeline or load a saved playthrough.
      </div>
    )
  }

  return (
    <div className="p-6 space-y-4">
      {/* Summary cards */}
      <div className="flex flex-wrap gap-3">
        <div className="rounded-lg px-4 py-2" style={{ background: 'var(--color-surface)' }}>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Locations</span>
          <p className="text-lg font-semibold">{stats.totalLocs.toLocaleString()}</p>
        </div>
        <div className="rounded-lg px-4 py-2" style={{ background: 'var(--color-surface)' }}>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Total Dev</span>
          <p className="text-lg font-semibold">{stats.totalDev.toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
        </div>
        <div className="rounded-lg px-4 py-2" style={{ background: 'var(--color-surface)' }}>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Total Pops</span>
          <p className="text-lg font-semibold">{stats.totalPops.toLocaleString()}</p>
        </div>
        {/* Rank breakdown mini-badges */}
        {Object.entries(stats.ranks).sort((a, b) => b[1] - a[1]).map(([rank, count]) => (
          <div key={rank} className="rounded-lg px-3 py-2" style={{ background: 'var(--color-surface)' }}>
            <span className="text-xs capitalize" style={{ color: RANK_COLORS[rank] || 'var(--color-text-muted)' }}>
              {rank.replace(/_/g, ' ')}
            </span>
            <p className="text-sm font-semibold">{count.toLocaleString()}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Rank</label>
          <select value={filterRank} onChange={(e) => setFilterRank(e.target.value)}
            className="px-2 py-1 rounded text-xs"
            style={{ background: 'var(--color-surface-alt)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}>
            <option value="all">All ranks</option>
            <option value="city">City</option>
            <option value="town">Town</option>
            <option value="rural_settlement">Rural Settlement</option>
          </select>
        </div>
        <div>
          <label className="block text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Integration</label>
          <select value={filterIntegration} onChange={(e) => setFilterIntegration(e.target.value)}
            className="px-2 py-1 rounded text-xs"
            style={{ background: 'var(--color-surface-alt)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}>
            <option value="all">All</option>
            <option value="core">Core</option>
            <option value="integrated">Integrated</option>
            <option value="conquered">Conquered</option>
            <option value="colonized">Colonized</option>
          </select>
        </div>
        <div>
          <label className="block text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Search</label>
          <input
            type="text"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Name, owner, region..."
            className="px-2 py-1 rounded text-xs w-48"
            style={{ background: 'var(--color-surface-alt)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}
          />
        </div>
        <span className="text-xs pb-1" style={{ color: 'var(--color-text-muted)' }}>
          Showing {displayData.length.toLocaleString()} / {locationData.length.toLocaleString()}
        </span>
      </div>

      {/* Location table */}
      <div className="rounded-lg overflow-hidden" style={{ background: 'var(--color-surface)' }}>
        <div className="overflow-x-auto max-h-[32rem] overflow-y-auto">
          {displayData.length === 0 && locationData.length === 0 ? (
            <p className="text-xs text-center py-8" style={{ color: 'var(--color-text-muted)' }}>
              {ptId ? 'Loading territory data...' : 'No location data available.'}
            </p>
          ) : displayData.length === 0 ? (
            <p className="text-xs text-center py-8" style={{ color: 'var(--color-text-muted)' }}>No location data available.</p>
          ) : (
            <table className="w-full text-xs">
              <thead className="sticky top-0">
                <tr style={{ background: 'var(--color-surface-alt)', color: 'var(--color-text-muted)' }}>
                  {/* Location column (sortable by location_id) */}
                  <th
                    className="text-left px-2 py-2 cursor-pointer hover:text-white select-none whitespace-nowrap"
                    onClick={() => handleSort('location_id')}
                  >
                    Location{sortIcon('location_id')}
                  </th>
                  {/* Owner column (sortable by owner_tag) */}
                  <th
                    className="text-left px-2 py-2 cursor-pointer hover:text-white select-none whitespace-nowrap"
                    onClick={() => handleSort('owner_tag')}
                  >
                    Owner{sortIcon('owner_tag')}
                  </th>
                  {/* Geography column with level selector embedded in header */}
                  <th className="text-left px-2 py-2 select-none whitespace-nowrap">
                    <select
                      value={geoLevel}
                      onChange={(e) => { setGeoLevel(e.target.value); setSortField(e.target.value) }}
                      className="px-1 py-0.5 rounded text-xs"
                      style={{
                        background: 'transparent',
                        color: 'inherit',
                        border: '1px solid var(--color-border)',
                      }}
                      title="Choose geography level"
                    >
                      {GEO_LEVELS.map((g) => (
                        <option key={g.key} value={g.key}>{g.label}</option>
                      ))}
                    </select>
                    <span
                      className="ml-1 cursor-pointer"
                      onClick={() => handleSort(geoLevel)}
                    >{sortIcon(geoLevel)}</span>
                  </th>
                  {/* Remaining pre-existing columns */}
                  {[
                    { key: 'rank', label: 'Rank' },
                    { key: 'development', label: 'Dev' },
                    { key: 'prosperity', label: 'Prosp' },
                    { key: 'pop_count', label: 'Pops' },
                    { key: 'tax', label: 'Tax' },
                    { key: 'integration_type', label: 'Integration' },
                    { key: 'culture_id', label: 'Culture' },
                    { key: 'religion_id', label: 'Religion' },
                    { key: 'garrison', label: 'Garrison' },
                    { key: 'language', label: 'Language' },
                  ].map((col) => (
                    <th
                      key={col.key}
                      className="text-left px-2 py-2 cursor-pointer hover:text-white select-none whitespace-nowrap"
                      onClick={() => handleSort(col.key)}
                    >
                      {col.label}{sortIcon(col.key)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {displayData.slice(0, 500).map((loc) => (
                  <tr key={loc.location_id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                    <td className="px-2 py-1 whitespace-nowrap">{fmtLocationCell(loc)}</td>
                    <td className="px-2 py-1 whitespace-nowrap">{fmtOwnerCell(loc)}</td>
                    <td className="px-2 py-1 whitespace-nowrap">{fmtGeoCell(loc)}</td>
                    <td className="px-2 py-1 capitalize" style={{ color: RANK_COLORS[loc.rank] }}>
                      {(loc.rank || '').replace('rural_settlement', 'rural')}
                    </td>
                    <td className="px-2 py-1">{(loc.development || 0).toFixed(1)}%</td>
                    <td className="px-2 py-1">{(loc.prosperity || 0).toFixed(1)}%</td>
                    <td className="px-2 py-1">{(loc.pop_count || 0).toLocaleString()}</td>
                    <td className="px-2 py-1">{(loc.tax || 0).toFixed(2)}</td>
                    <td className="px-2 py-1 capitalize" style={{ color: INTEGRATION_COLORS[loc.integration_type] }}>
                      {loc.integration_type || 'none'}
                    </td>
                    <td className="px-2 py-1">{gameLoc ? gameLoc.fmtCulture(loc.culture_id) : loc.culture_id}</td>
                    <td className="px-2 py-1">{gameLoc ? gameLoc.fmtReligion(loc.religion_id) : loc.religion_id}</td>
                    <td className="px-2 py-1">{(loc.garrison || 0).toFixed(2)}</td>
                    <td className="px-2 py-1 capitalize">{(loc.language || '').replace(/_/g, ' ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {displayData.length > 500 && (
            <p className="text-xs px-3 py-2" style={{ color: 'var(--color-text-muted)' }}>
              Showing first 500 of {displayData.length.toLocaleString()} locations. Use filters to narrow results.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

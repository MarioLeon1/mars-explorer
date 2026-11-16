import { useMemo } from 'react'
import { api } from '../../api/client'
import { useApi } from '../../api/useApi'
import { useSystemStatus } from '../../app/systemStatus'
import { Panel } from '../../design-system/Panel'
import { DataList, SkeletonBlock } from '../../design-system/primitives'
import { formatBytes, formatSol, formatUtc } from '../../lib/format'
import { countByGroup } from './grouping'

export function ArchivePanel() {
  const cameras = useApi('cameras', api.cameras)
  const { state: status } = useSystemStatus()
  const groups = useMemo(() => countByGroup(cameras.state.data ?? []), [cameras.state.data])
  const max = Math.max(1, ...groups.map((g) => g.count))
  const system = status.data

  return (
    <Panel title="Local archive" className="archive" scroll>
      {cameras.state.status === 'loading' ? (
        <SkeletonBlock lines={4} />
      ) : (
        <ul className="archive__bars" aria-label="Images per camera group">
          {groups.map((g) => (
            <li key={g.group}>
              <span className="archive__name">{g.label}</span>
              <span className="archive__track" aria-hidden="true">
                <span className="archive__bar" style={{ width: `${(g.count / max) * 100}%` }} />
              </span>
              <span className="archive__count mono">{g.count}</span>
            </li>
          ))}
        </ul>
      )}
      {system && (
        <DataList
          items={[
            { label: 'Stored', value: `${system.database.images} images · ${system.database.sols} sols` },
            { label: 'Disk', value: `${formatBytes(system.storage.bytes)} · ${system.storage.image_files} files` },
            {
              label: 'Last ingest',
              value: system.last_ingest ? `${system.last_ingest.kind} · ${system.last_ingest.status}` : 'never',
            },
            {
              label: 'NASA feed',
              value: system.feed?.latest_sol != null ? `sol ${formatSol(system.feed.latest_sol)}` : '—',
              hint: system.feed ? `Latest sol in NASA's raw feed, checked ${formatUtc(system.feed.checked_at)}` : undefined,
            },
          ]}
        />
      )}
    </Panel>
  )
}

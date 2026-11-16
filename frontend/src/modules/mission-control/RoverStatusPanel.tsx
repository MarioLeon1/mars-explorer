import { api } from '../../api/client'
import { useApi } from '../../api/useApi'
import { Panel } from '../../design-system/Panel'
import { ProvenanceBadge } from '../../design-system/ProvenanceBadge'
import { CommandHint, DataList, ErrorState, SkeletonBlock } from '../../design-system/primitives'
import {
  formatDegrees,
  formatKilometres,
  formatLatitude,
  formatLongitude,
  formatMetres,
  formatSol,
  formatUtcDate,
} from '../../lib/format'

export function RoverStatusPanel() {
  const { state, retry } = useApi('rover-position', api.roverPosition)
  const position = state.data

  return (
    <Panel
      title="Rover localization"
      className="rover"
      meta={position && <ProvenanceBadge provenance={position.provenance} credit="JPL" />}
    >
      {state.status === 'loading' && <SkeletonBlock lines={6} />}
      {state.status === 'error' &&
        (state.error.code === 'no_position_data' ? (
          <ErrorState title="No localizations ingested" message="Fetch the real rover positions published by JPL:">
            <CommandHint command="cd backend; uv run mars-ingest waypoints" />
          </ErrorState>
        ) : (
          <ErrorState title="Position unavailable" message={state.error.message} onRetry={retry} />
        ))}
      {position && (
        <>
          <div className="rover__headline">
            <div>
              <span className="label">Last fix</span>
              <span className="rover__sol mono">SOL {formatSol(position.sol)}</span>
            </div>
            <div>
              <span className="label">Odometry</span>
              <span className="rover__odo mono">{formatKilometres(position.odometry_total_m)}</span>
            </div>
          </div>
          <DataList
            columns={2}
            items={[
              { label: 'Lat', value: formatLatitude(position.lat) },
              { label: 'Lon', value: formatLongitude(position.lon) },
              {
                label: 'Elev.',
                value: formatMetres(position.elevation_m),
                hint: 'Relative to the Mars areoid (reference surface)',
              },
              { label: 'Last drive', value: formatMetres(position.drive_distance_m) },
              { label: 'Site/drive', value: `${position.site ?? '—'} / ${position.drive ?? '—'}` },
              { label: 'Heading', value: formatDegrees(position.yaw_deg), hint: 'Yaw' },
              { label: 'Roll', value: formatDegrees(position.roll_deg) },
              { label: 'Pitch', value: formatDegrees(position.pitch_deg) },
            ]}
          />
          <p className="rover__note">
            {position.note ?? 'Localization'} · retrieved {formatUtcDate(position.source.retrieved_at)} from{' '}
            <a href={position.source.url} target="_blank" rel="noopener noreferrer">
              JPL MMGIS
            </a>
          </p>
          <ul className="rover__caveats">
            {position.caveats.map((caveat) => (
              <li key={caveat}>{caveat}</li>
            ))}
            <li>No power, thermal or battery data is shown: NASA does not publish real-time telemetry.</li>
          </ul>
        </>
      )}
    </Panel>
  )
}

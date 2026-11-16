import type { ApiState } from '../../api/useApi'
import type { ImageDetail, ImageSummary } from '../../api/types'
import { Panel } from '../../design-system/Panel'
import { DataList, ErrorState, SkeletonBlock } from '../../design-system/primitives'
import { formatDegrees, formatNumber, formatUtc } from '../../lib/format'

interface ObservationPanelProps {
  summary: ImageSummary | null
  detail: ApiState<ImageDetail>
}

export function ObservationPanel({ summary, detail }: ObservationPanelProps) {
  const data = detail.data && summary && detail.data.image_id === summary.image_id ? detail.data : null

  return (
    <Panel title="Selected observation" scroll className="obs">
      {!summary || (detail.status === 'loading' && !data) ? (
        <SkeletonBlock lines={9} />
      ) : detail.status === 'error' ? (
        <ErrorState title="Metadata unavailable" message={detail.error.message} />
      ) : data ? (
        <>
          <p className="obs__title">{data.title ?? data.camera.label}</p>
          <DataList
            items={[
              { label: 'Camera', value: data.camera.instrument },
              { label: 'Sol', value: data.sol },
              { label: 'Taken', value: formatUtc(data.date_taken_utc), hint: 'Spacecraft time converted to UTC' },
              { label: 'Local solar', value: data.lmst ? `${data.lmst} LMST` : '—', hint: 'Local Mean Solar Time at the rover' },
              { label: 'Received', value: formatUtc(data.date_received), hint: 'When the data reached Earth' },
              { label: 'Site / drive', value: `${data.site ?? '—'} / ${data.drive ?? '—'}` },
              { label: 'Mast az / el', value: `${formatDegrees(data.mast_az, 1)} / ${formatDegrees(data.mast_el, 1)}` },
              {
                label: 'Downsample',
                value: data.scale_factor ? `×${formatNumber(data.scale_factor, 0)}` : '—',
                hint: 'On-board downsampling factor before transmission',
              },
              { label: 'Filter', value: data.filter_name ?? '—' },
              { label: 'Sequence', value: data.sequence_id ?? '—', hint: 'Command sequence id parsed from the product id' },
              { label: 'Camera model', value: data.camera_model_type ?? '—' },
            ]}
          />
          <ul className="obs__notes">
            {data.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
          <p className="obs__credit">
            Credit: {data.credit ?? 'NASA/JPL-Caltech'} · original record preserved locally
          </p>
        </>
      ) : null}
    </Panel>
  )
}

import { useState } from 'react'
import { api } from '../../api/client'
import type { ImageDetail } from '../../api/types'
import { useApi } from '../../api/useApi'
import { IconExternal } from '../../design-system/icons'
import { ProvenanceBadge } from '../../design-system/ProvenanceBadge'
import { DataList, ErrorState, SkeletonBlock } from '../../design-system/primitives'
import { formatDegrees, formatNumber, formatUtc } from '../../lib/format'

function vector(values: number[] | null, digits = 3): string {
  return values ? `(${values.map((v) => v.toFixed(digits)).join(', ')})` : '—'
}

function RawRecordView({ imageId }: { imageId: string }) {
  const { state, retry } = useApi(`raw:${imageId}`, (signal) => api.raw(imageId, signal))
  if (state.status === 'loading') return <SkeletonBlock lines={6} />
  if (state.status === 'error') return <ErrorState title="Raw record unavailable" message={state.error.message} onRetry={retry} />
  return <pre className="insp__raw mono">{JSON.stringify(state.data.record, null, 2)}</pre>
}

export function Inspector({ detail }: { detail: ImageDetail }) {
  const [showRaw, setShowRaw] = useState(false)
  const files = detail.source.original_files

  return (
    <div className="insp">
      <div className="insp__head">
        <ProvenanceBadge provenance={detail.provenance} credit={detail.credit} />
        <p className="insp__title">{detail.title ?? detail.camera.label}</p>
      </div>

      <section className="insp__section">
        <h3 className="label">Identification</h3>
        <DataList
          items={[
            { label: 'Camera', value: detail.camera.instrument, hint: detail.camera.label },
            { label: 'Sol', value: detail.sol },
            { label: 'Site / drive', value: `${detail.site ?? '—'} / ${detail.drive ?? '—'}`, hint: 'Rover location counters' },
            { label: 'Sequence', value: detail.sequence_id ?? '—', hint: 'Command sequence id parsed from the product id' },
            { label: 'Sample', value: detail.sample_type },
          ]}
        />
      </section>

      <section className="insp__section">
        <h3 className="label">Time</h3>
        <DataList
          items={[
            { label: 'Taken', value: formatUtc(detail.date_taken_utc) },
            { label: 'Local solar', value: detail.lmst ? `${detail.lmst} LMST` : '—', hint: 'Local Mean Solar Time at the rover' },
            { label: 'Received', value: formatUtc(detail.date_received), hint: 'When the data reached Earth' },
            { label: 'SCLK', value: formatNumber(detail.sclk, 3), hint: 'Spacecraft clock (seconds)' },
          ]}
        />
      </section>

      <section className="insp__section">
        <h3 className="label">Pointing &amp; camera model</h3>
        <DataList
          items={[
            { label: 'Mast az / el', value: `${formatDegrees(detail.mast_az, 2)} / ${formatDegrees(detail.mast_el, 2)}` },
            { label: 'Model', value: detail.camera_model_type ?? '—', hint: 'CAHV-family photogrammetric camera model' },
            { label: 'Cam. position', value: vector(detail.camera_position), hint: 'Camera centre (C vector), rover frame, metres' },
            { label: 'Cam. vector', value: vector(detail.camera_vector), hint: 'Pointing (A vector)' },
            { label: 'Rover attitude', value: vector(detail.attitude_quaternion, 4), hint: 'Quaternion as published' },
          ]}
        />
      </section>

      <section className="insp__section">
        <h3 className="label">Image product</h3>
        <DataList
          items={[
            { label: 'Dimensions', value: detail.width && detail.height ? `${detail.width} × ${detail.height} px` : '—' },
            { label: 'Downsample', value: detail.scale_factor ? `×${formatNumber(detail.scale_factor, 0)}` : '—', hint: 'On-board downsampling factor' },
            { label: 'Subframe', value: detail.subframe_rect ? detail.subframe_rect.join(', ') : '—', hint: 'Sensor region: x, y, width, height' },
            { label: 'Filter', value: detail.filter_name ?? '—' },
          ]}
        />
        <ul className="insp__notes">
          {detail.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </section>

      <section className="insp__section">
        <h3 className="label">Source</h3>
        <ul className="insp__links">
          {detail.source.nasa_page_url && (
            <li>
              <a href={detail.source.nasa_page_url} target="_blank" rel="noopener noreferrer">
                NASA raw-image page <IconExternal />
              </a>
            </li>
          )}
          {detail.source.nasa_json_url && (
            <li>
              <a href={detail.source.nasa_json_url} target="_blank" rel="noopener noreferrer">
                NASA JSON record <IconExternal />
              </a>
            </li>
          )}
          {files.full_res && (
            <li>
              <a href={files.full_res} target="_blank" rel="noopener noreferrer">
                Original full-resolution file <IconExternal />
              </a>
            </li>
          )}
        </ul>
        <p className="insp__cached mono">
          cached locally: {(['small', 'large', 'full_res'] as const).filter((s) => detail.local_files[s]).join(', ') || 'none'}
        </p>
        <button type="button" className="ds-button" aria-expanded={showRaw} onClick={() => setShowRaw((v) => !v)}>
          {showRaw ? 'Hide' : 'Show'} original NASA record
        </button>
        {showRaw && <RawRecordView imageId={detail.image_id} />}
      </section>
    </div>
  )
}

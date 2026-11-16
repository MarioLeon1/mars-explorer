import { useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { ImageSummary } from '../../api/types'
import { useApi } from '../../api/useApi'
import { ErrorState, Skeleton } from '../../design-system/primitives'
import { shortInstrument } from '../../lib/cameras'

interface RelatedPanelProps {
  imageId: string
  dataVersion: number
  onOpen: (imageId: string) => void
  onCompare: (image: ImageSummary, stereo: boolean) => void
  onDataChanged: () => void
}

function Thumb({
  image,
  onOpen,
  onCompare,
  badge,
}: {
  image: ImageSummary
  onOpen: () => void
  onCompare: () => void
  badge?: string
}) {
  return (
    <div className="rel__item">
      <button type="button" className="rel__thumb" onClick={onOpen} title={`Open ${image.image_id}`}>
        <img src={image.thumb_url} alt={`${image.camera.instrument}, sol ${image.sol}`} loading="lazy" />
        <span className="rel__cam mono">{shortInstrument(image.camera.instrument)}</span>
        {badge && <span className="rel__badge">{badge}</span>}
      </button>
      <button type="button" className="rel__compare" onClick={onCompare}>
        Compare
      </button>
    </div>
  )
}

type StereoFetch = { state: 'idle' | 'loading' } | { state: 'error'; message: string; notPublished: boolean }

export function RelatedPanel({ imageId, dataVersion, onOpen, onCompare, onDataChanged }: RelatedPanelProps) {
  const { state, retry } = useApi(`related:${imageId}:${dataVersion}`, (signal) => api.related(imageId, signal))
  const [fetchState, setFetchState] = useState<StereoFetch>({ state: 'idle' })

  const fetchPartner = async () => {
    setFetchState({ state: 'loading' })
    try {
      await api.fetchStereoPartner(imageId)
      setFetchState({ state: 'idle' })
      onDataChanged()
    } catch (error) {
      const apiError = error instanceof ApiError ? error : null
      setFetchState({
        state: 'error',
        message: apiError?.message ?? String(error),
        notPublished: apiError?.code === 'stereo_partner_not_found',
      })
    }
  }

  if (state.status === 'loading') {
    return (
      <div className="rel">
        <Skeleton height={92} />
      </div>
    )
  }
  if (state.status === 'error') {
    return <ErrorState title="Related images unavailable" message={state.error.message} onRetry={retry} />
  }

  const { stereo, same_sequence: sequence, same_sol_other_cameras: others } = state.data

  return (
    <div className="rel">
      {stereo && (
        <section className="rel__group rel__group--stereo" aria-label="Stereo pair">
          <h3 className="label">Stereo pair · {stereo.partner_instrument.replace(/_/g, ' ')}</h3>
          {stereo.local ? (
            <Thumb
              image={stereo.local}
              badge="STEREO"
              onOpen={() => onOpen(stereo.local!.image_id)}
              onCompare={() => onCompare(stereo.local!, true)}
            />
          ) : (
            <div className="rel__fetch">
              <p>The other eye is not stored locally.</p>
              <button
                type="button"
                className="ds-button"
                onClick={fetchPartner}
                disabled={fetchState.state === 'loading' || (fetchState.state === 'error' && fetchState.notPublished)}
              >
                {fetchState.state === 'loading' ? 'Checking NASA…' : 'Fetch from NASA'}
              </button>
              {fetchState.state === 'error' && (
                <p className={fetchState.notPublished ? 'rel__note' : 'rel__error'} role="status">
                  {fetchState.notPublished
                    ? 'NASA has not published a matching frame for this one (common for sky/movie sequences and narrow-band Mastcam-Z filters).'
                    : fetchState.message}
                </p>
              )}
            </div>
          )}
        </section>
      )}

      <section className="rel__group" aria-label="Same sequence">
        <h3 className="label">Same sequence · {sequence.length}</h3>
        {sequence.length === 0 ? (
          <p className="rel__empty">No other stored frames from this command sequence.</p>
        ) : (
          <div className="rel__row">
            {sequence.map((image) => (
              <Thumb key={image.image_id} image={image} onOpen={() => onOpen(image.image_id)} onCompare={() => onCompare(image, false)} />
            ))}
          </div>
        )}
      </section>

      <section className="rel__group" aria-label="Other cameras on the same sol">
        <h3 className="label">Same sol, other cameras · {others.length}</h3>
        {others.length === 0 ? (
          <p className="rel__empty">No other cameras stored for this sol.</p>
        ) : (
          <div className="rel__row">
            {others.map((image) => (
              <Thumb key={image.image_id} image={image} onOpen={() => onOpen(image.image_id)} onCompare={() => onCompare(image, false)} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

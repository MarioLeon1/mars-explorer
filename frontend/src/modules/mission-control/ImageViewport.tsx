import { useState } from 'react'
import type { ImageDetail, ImageSummary } from '../../api/types'
import { IconExternal } from '../../design-system/icons'
import { ProvenanceBadge } from '../../design-system/ProvenanceBadge'
import { formatDegrees, formatSol } from '../../lib/format'

interface ImageViewportProps {
  summary: ImageSummary | null
  detail: ImageDetail | null
  loading: boolean
  position: { index: number; total: number } | null
  onStep: (delta: number) => void
}

export function ImageViewport({ summary, detail, loading, position, onStep }: ImageViewportProps) {
  // Track load state per URL so switching images shows the shimmer until the new one arrives.
  const [loadedUrl, setLoadedUrl] = useState<string | null>(null)
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  const url = summary?.preview_url ?? null
  const ready = url !== null && loadedUrl === url
  const failed = url !== null && failedUrl === url
  const matchingDetail = detail && summary && detail.image_id === summary.image_id ? detail : null

  return (
    <section className="viewport" aria-label="Selected observation">
      <div className={`viewport__frame${ready ? ' is-ready' : ''}`}>
        {url && !failed && (
          <img
            key={url}
            src={url}
            alt={
              summary
                ? `${summary.camera.label}, sol ${summary.sol}${summary.lmst ? `, ${summary.lmst} LMST` : ''}`
                : ''
            }
            onLoad={() => setLoadedUrl(url)}
            onError={() => setFailedUrl(url)}
          />
        )}
        {(loading || (url && !ready && !failed)) && <div className="viewport__shimmer" aria-hidden="true" />}
        {failed && (
          <p className="viewport__message">
            Image unavailable — the backend could not fetch it from NASA. Check your connection and retry.
          </p>
        )}

        <span className="viewport__corner viewport__corner--tl" aria-hidden="true" />
        <span className="viewport__corner viewport__corner--tr" aria-hidden="true" />
        <span className="viewport__corner viewport__corner--bl" aria-hidden="true" />
        <span className="viewport__corner viewport__corner--br" aria-hidden="true" />

        {summary && (
          <>
            <div className="viewport__hud viewport__hud--top">
              <div>
                <span className="viewport__sol mono">SOL {formatSol(summary.sol)}</span>
                <span className="viewport__camera">{summary.camera.label}</span>
              </div>
              <ProvenanceBadge provenance={summary.provenance} credit={summary.credit} />
            </div>
            <div className="viewport__hud viewport__hud--bottom">
              <dl className="viewport__readouts mono">
                <div>
                  <dt>LMST</dt>
                  <dd>{summary.lmst ?? '—'}</dd>
                </div>
                <div>
                  <dt>MAST AZ</dt>
                  <dd>{formatDegrees(matchingDetail?.mast_az, 2)}</dd>
                </div>
                <div>
                  <dt>MAST EL</dt>
                  <dd>{formatDegrees(matchingDetail?.mast_el, 2)}</dd>
                </div>
                <div>
                  <dt>FRAME</dt>
                  <dd>{summary.width && summary.height ? `${summary.width}×${summary.height}` : '—'}</dd>
                </div>
              </dl>
              {matchingDetail?.source.nasa_page_url && (
                <a
                  className="viewport__link"
                  href={matchingDetail.source.nasa_page_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  View on NASA <IconExternal />
                </a>
              )}
            </div>
          </>
        )}

        {position && (
          <>
            <button
              type="button"
              className="viewport__step viewport__step--prev"
              onClick={() => onStep(-1)}
              disabled={position.index === 0}
              aria-label="Newer observation (left arrow)"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                <path d="M10 3L5 8l5 5" fill="none" stroke="currentColor" strokeWidth="1.5" />
              </svg>
            </button>
            <button
              type="button"
              className="viewport__step viewport__step--next"
              onClick={() => onStep(1)}
              disabled={position.index >= position.total - 1}
              aria-label="Older observation (right arrow)"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                <path d="M6 3l5 5-5 5" fill="none" stroke="currentColor" strokeWidth="1.5" />
              </svg>
            </button>
          </>
        )}
      </div>
      {summary && (
        <p className="viewport__id mono" title="NASA product identifier">
          {summary.image_id}
          {position && (
            <span className="viewport__count">
              {position.index + 1} / {position.total}
            </span>
          )}
        </p>
      )}
    </section>
  )
}

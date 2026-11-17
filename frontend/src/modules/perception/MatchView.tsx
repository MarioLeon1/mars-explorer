import { useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { ImageSummary, MatchResult } from '../../api/types'
import { ProvenanceBadge } from '../../design-system/ProvenanceBadge'
import { DataList, ErrorState, SkeletonBlock } from '../../design-system/primitives'

interface MatchViewProps {
  left: ImageSummary
  right: ImageSummary
}

const px = (v: number | undefined) => (v === undefined ? '—' : `${v.toFixed(1)} px`)

/** Feature correspondences between the two eyes of a verified stereo pair. */
export function MatchView({ left, right }: MatchViewProps) {
  const [result, setResult] = useState<MatchResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [showOutliers, setShowOutliers] = useState(false)

  const run = async () => {
    setRunning(true)
    setError(null)
    try {
      setResult(await api.match(left.image_id, right.image_id))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  const gap = 16
  const width = result ? result.width_a + gap + result.width_b : 0
  const height = result ? Math.max(result.height_a, result.height_b) : 0
  const shown = result?.matches.filter((m) => m.inlier || showOutliers) ?? []

  return (
    <div className="mv">
      <div className="mv__bar">
        <button type="button" className="ds-button xi__go" onClick={run} disabled={running}>
          {running ? 'Matching…' : result ? 'Run again' : 'Match features'}
        </button>
        <label className="pf__bool">
          <input type="checkbox" checked={showOutliers} onChange={(e) => setShowOutliers(e.target.checked)} disabled={!result} />
          <span>Show rejected matches</span>
        </label>
        <p className="mv__note">ORB features → ratio test → RANSAC epipolar geometry. Lines join the same feature in both eyes.</p>
      </div>
      <div className="mv__body">
        <div className="mv__canvas">
          {error ? (
            <ErrorState title="Matching failed" message={error} onRetry={run} />
          ) : running && !result ? (
            <SkeletonBlock lines={10} />
          ) : result ? (
            <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${result.inliers} feature matches between left and right images`}>
              <image href={left.preview_url} x={0} y={0} width={result.width_a} height={result.height_a} />
              <image href={right.preview_url} x={result.width_a + gap} y={0} width={result.width_b} height={result.height_b} />
              {shown.map((m, i) => (
                <line
                  key={i}
                  className={m.inlier ? 'mv__in' : 'mv__out'}
                  x1={m.ax}
                  y1={m.ay}
                  x2={m.bx + result.width_a + gap}
                  y2={m.by}
                />
              ))}
            </svg>
          ) : (
            <div className="mv__placeholder">
              <img src={left.thumb_url} alt="Left eye" />
              <img src={right.thumb_url} alt="Right eye" />
            </div>
          )}
        </div>
        {result && (
          <aside className="mv__stats">
            <ProvenanceBadge provenance={result.provenance} credit="Mars Explorer" />
            <DataList
              items={[
                { label: 'Keypoints L / R', value: `${result.keypoints_a} / ${result.keypoints_b}` },
                { label: 'Ratio-test matches', value: result.tentative },
                { label: 'RANSAC inliers', value: result.inliers },
                { label: 'Inlier ratio', value: result.inlier_ratio === null ? '—' : `${(result.inlier_ratio * 100).toFixed(0)} %` },
                { label: 'Disparity dx (median)', value: px(result.disparity.dx_median_px), hint: 'Right − left horizontal offset' },
                { label: 'dx spread (IQR)', value: px(result.disparity.dx_iqr_px), hint: 'Varies with depth: nearer surfaces shift more' },
                { label: 'Vertical dy (median)', value: px(result.disparity.dy_median_px), hint: 'Near zero for a well-rectified pair' },
                { label: 'Compute', value: `${result.elapsed_ms.toFixed(0)} ms` },
              ]}
            />
            <ul className="rp__limits">
              {result.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </aside>
        )}
      </div>
    </div>
  )
}

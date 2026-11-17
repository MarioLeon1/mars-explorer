import type { OfficialVideo } from '../../api/types'
import { ProvenanceBadge } from '../../design-system/ProvenanceBadge'

/** An official NASA video, streamed from the NASA Image and Video Library. */
export function OfficialVideoPlayer({ video }: { video: OfficialVideo }) {
  return (
    <div className="rp-player">
      <div className="rp-player__stage">
        <video key={video.video_url} src={video.video_url} poster={video.poster_url} controls preload="metadata">
          Your browser cannot play this video. <a href={video.page_url}>Open it on images.nasa.gov</a>.
        </video>
        <span className="rp-player__stamp rp-player__stamp--official">OFFICIAL NASA VIDEO</span>
      </div>
      <div className="rp-player__meta">
        <ProvenanceBadge provenance={video.provenance} credit={video.credit} />
        <span>{video.title}</span>
        <span className="mono">{video.date}</span>
        {video.sol !== null && (
          <span>
            sol <span className="mono">{video.sol}</span>
          </span>
        )}
      </div>
      <p className="rp-card__text">{video.description}</p>
      <p className="rp-note">
        Streamed from the NASA Image and Video Library —{' '}
        <a href={video.page_url} target="_blank" rel="noreferrer">
          source page
        </a>
        . Edited and published by NASA/JPL; shown unmodified.
      </p>
    </div>
  )
}

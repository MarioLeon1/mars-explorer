import { useCallback, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { FeaturedSequence, SequenceSummary, TimelineImage } from '../../api/types'
import { useApi } from '../../api/useApi'
import { Panel } from '../../design-system/Panel'
import { ProvenanceBadge } from '../../design-system/ProvenanceBadge'
import { CommandHint, EmptyState, ErrorState, SkeletonBlock } from '../../design-system/primitives'
import { formatKilometres } from '../../lib/format'
import '../perception/perception.css'
import { FeaturedSequences } from './FeaturedSequences'
import { MissionStrip } from './MissionStrip'
import { OfficialVideoPlayer } from './OfficialVideoPlayer'
import { formatOffset, KIND_LABEL } from './playback'
import './replay.css'
import { SequencePlayer } from './SequencePlayer'
import { SolTimelineChart } from './SolTimelineChart'

const PLAYABLE_MIN_FRAMES = 3

function defaultSequence(sequences: SequenceSummary[]): string | null {
  const playable = sequences.filter((s) => s.frame_count >= PLAYABLE_MIN_FRAMES && s.kind !== 'single_exposure')
  const preferred = playable.find((s) => s.kind === 'fixed_pointing' || s.kind === 'vehicle_fixed') ?? playable[0]
  return preferred?.id ?? null
}

export function Replay() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [reload, setReload] = useState(0)

  const mission = useApi(`replay-mission-${reload}`, api.replayMission)
  const featured = useApi(`replay-featured-${reload}`, api.featured)
  const videos = useApi('replay-videos', api.videos)

  const solParam = params.get('sol')
  const imageSols = (mission.state.data?.sols ?? []).filter((s) => s.images > 0)
  const sol = solParam !== null && /^\d+$/.test(solParam) ? Number(solParam) : (imageSols[imageSols.length - 1]?.sol ?? null)
  const timeline = useApi(sol === null ? null : `replay-sol-${sol}-${reload}`, (signal) => api.replaySol(sol ?? 0, signal))

  const videoParam = params.get('video')
  const video = videoParam !== null ? videos.state.data?.find((v) => v.nasa_id === videoParam) : undefined
  const seqParam = params.get('seq')
  const sequenceId =
    videoParam !== null ? null : (seqParam ?? (timeline.state.data ? defaultSequence(timeline.state.data.sequences) : null))
  const sequence = useApi(sequenceId === null ? null : `replay-seq-${sequenceId}-${reload}`, (signal) =>
    api.sequence(sequenceId ?? '', signal),
  )

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params)
    for (const [k, v] of Object.entries(changes)) {
      if (v === null) next.delete(k)
      else next.set(k, v)
    }
    setParams(next)
  }
  const selectSol = (value: number) => update({ sol: String(value), seq: null, video: null })
  const selectSequence = (id: string, solValue: number) => update({ sol: String(solValue), seq: id, video: null })
  const onDownloaded = useCallback(() => setReload((n) => n + 1), [])

  const onImage = (image: TimelineImage) => {
    const match = timeline.state.data?.sequences.find(
      (s) => s.camera.instrument === image.camera.instrument && s.sequence_id === image.sequence_id,
    )
    if (match && match.frame_count >= 2) selectSequence(match.id, match.sol)
    else navigate(`/explorer/${image.image_id}`)
  }
  const playFeatured = (item: FeaturedSequence) => {
    const id = item.sequence_url?.split('/').pop()
    if (id) selectSequence(decodeURIComponent(id), item.sol)
  }

  const missionData = mission.state.data
  const timelineData = timeline.state.data

  return (
    <div className="rp">
      <div className="rp-main">
        <Panel
          title="Mission timeline · real drive distance per sol"
          meta={
            missionData && (
              <>
                <span className="mono">{formatKilometres(missionData.total_drive_m)}</span> over{' '}
                <span className="mono">{missionData.drive_sols}</span> sols{' '}
                <ProvenanceBadge provenance={missionData.provenance} credit="NASA/JPL-Caltech" />
              </>
            )
          }
        >
          {mission.state.status === 'loading' && <SkeletonBlock lines={3} />}
          {mission.state.status === 'error' && (
            <ErrorState title="Mission timeline unavailable" message={mission.state.error.message} onRetry={mission.retry} />
          )}
          {missionData &&
            (missionData.sols.length === 0 ? (
              <EmptyState title="No data yet">
                <p>Download images and drives first:</p>
                <CommandHint command="cd backend; uv run mars-ingest seed" />
              </EmptyState>
            ) : (
              <MissionStrip sols={missionData.sols} selected={sol} onSelect={selectSol} />
            ))}
        </Panel>

        <Panel
          title={sol === null ? 'Sol timeline' : `Sol ${sol} timeline`}
          meta={
            timelineData && (
              <span className="rp-solnav">
                <button
                  type="button"
                  className="ds-button"
                  disabled={timelineData.previous_sol === null}
                  onClick={() => timelineData.previous_sol !== null && selectSol(timelineData.previous_sol)}
                >
                  ◀ {timelineData.previous_sol ?? ''}
                </button>
                <button
                  type="button"
                  className="ds-button"
                  disabled={timelineData.next_sol === null}
                  onClick={() => timelineData.next_sol !== null && selectSol(timelineData.next_sol)}
                >
                  {timelineData.next_sol ?? ''} ▶
                </button>
              </span>
            )
          }
        >
          {timeline.state.status === 'loading' && sol !== null && <SkeletonBlock lines={4} />}
          {timeline.state.status === 'error' && (
            <ErrorState title={`Nothing stored for sol ${sol}`} message={timeline.state.error.message} onRetry={timeline.retry}>
              <p>Pick a sol with a tick on the mission timeline, or download it from the Explorer.</p>
            </ErrorState>
          )}
          {timelineData && (
            <>
              {timelineData.images.length === 0 && (
                <p className="rp-note">
                  No images of this sol are stored — only the real drive. Download them from the Explorer to see the
                  imaging timeline.
                </p>
              )}
              <SolTimelineChart timeline={timelineData} activeSequence={sequenceId} onImage={onImage} />
            </>
          )}
        </Panel>

        <Panel title={video ? 'Official NASA video' : 'Reconstructed sequence'} className="rp-viewer">
          {video && <OfficialVideoPlayer video={video} />}
          {!video && sequenceId === null && (
            <EmptyState title="Nothing to play for this sol">
              <p>
                Choose a sequence from the list, download a featured sequence, or watch an official NASA video on the
                right.
              </p>
            </EmptyState>
          )}
          {!video && sequenceId !== null && sequence.state.status === 'loading' && <SkeletonBlock lines={6} />}
          {!video && sequence.state.status === 'error' && (
            <ErrorState title="Sequence unavailable" message={sequence.state.error.message} onRetry={sequence.retry} />
          )}
          {!video && sequence.state.data && <SequencePlayer key={sequence.state.data.id} sequence={sequence.state.data} />}
        </Panel>
      </div>

      <aside className="rp-side">
        <Panel title="Sequences this sol" meta={timelineData && <span className="mono">{timelineData.sequences.length}</span>}>
          {timelineData && timelineData.sequences.length === 0 && (
            <p className="rp-note">No groups of two or more frames from one command sequence are stored for this sol.</p>
          )}
          <ul className="rp-list">
            {timelineData?.sequences.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  className={`rp-seq ${s.id === sequenceId ? 'is-active' : ''}`}
                  onClick={() => selectSequence(s.id, s.sol)}
                  aria-pressed={s.id === sequenceId}
                >
                  <img src={s.thumb_url} alt="" width={56} height={42} loading="lazy" />
                  <span className="rp-seq__text">
                    <span className="rp-seq__title">{s.camera.instrument.replaceAll('_', ' ')}</span>
                    <span className="rp-seq__meta">
                      <span className="mono">{s.frame_count}</span> frames · {KIND_LABEL[s.kind]}
                    </span>
                    <span className="rp-seq__meta">
                      LMST <span className="mono">{s.start_lmst ?? '—'}</span> · span{' '}
                      <span className="mono">{formatOffset(s.duration_s).replace('+', '')}</span>
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Featured sequences">
          {featured.state.status === 'loading' && <SkeletonBlock lines={4} />}
          {featured.state.status === 'error' && (
            <ErrorState title="Unavailable" message={featured.state.error.message} onRetry={featured.retry} />
          )}
          {featured.state.data && (
            <FeaturedSequences items={featured.state.data} onPlay={playFeatured} onDownloaded={onDownloaded} />
          )}
        </Panel>

        <Panel title="Official NASA videos">
          {videos.state.status === 'loading' && <SkeletonBlock lines={3} />}
          {videos.state.status === 'error' && (
            <ErrorState title="Unavailable" message={videos.state.error.message} onRetry={videos.retry} />
          )}
          <ul className="rp-list">
            {videos.state.data?.map((v) => (
              <li key={v.nasa_id}>
                <button
                  type="button"
                  className={`rp-seq ${v.nasa_id === videoParam ? 'is-active' : ''}`}
                  aria-pressed={v.nasa_id === videoParam}
                  onClick={() => update({ video: v.nasa_id, seq: null })}
                >
                  <img src={v.poster_url} alt="" width={56} height={42} loading="lazy" />
                  <span className="rp-seq__text">
                    <span className="rp-seq__title">{v.title}</span>
                    <span className="rp-seq__meta">
                      <span className="mono">{v.date}</span> · {v.credit}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Panel>
      </aside>
    </div>
  )
}

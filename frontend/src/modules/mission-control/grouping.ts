import type { CameraGroup, CameraWithCount, ImageSummary } from '../../api/types'

export interface SolGroup {
  sol: number
  items: ImageSummary[]
}

/** Group consecutive observations of the same sol (input is already sorted by sol). */
export function groupBySol(items: ImageSummary[]): SolGroup[] {
  const groups: SolGroup[] = []
  for (const item of items) {
    const last = groups[groups.length - 1]
    if (last && last.sol === item.sol) last.items.push(item)
    else groups.push({ sol: item.sol, items: [item] })
  }
  return groups
}

export const GROUP_LABELS: Record<CameraGroup, string> = {
  navcam: 'Navcam',
  hazcam_front: 'Front Hazcam',
  hazcam_rear: 'Rear Hazcam',
  mastcamz: 'Mastcam-Z',
  skycam: 'SkyCam',
  supercam: 'SuperCam',
  sherloc: 'SHERLOC',
  pixl: 'PIXL',
  cachecam: 'CacheCam',
  edl: 'EDL cameras',
  helicopter: 'Ingenuity',
  other: 'Other',
}

export interface GroupCount {
  group: CameraGroup
  label: string
  count: number
}

/** Sum image counts per camera group, keeping catalogue order and dropping empty groups. */
export function countByGroup(cameras: CameraWithCount[]): GroupCount[] {
  const totals = new Map<CameraGroup, number>()
  for (const camera of cameras) totals.set(camera.group, (totals.get(camera.group) ?? 0) + camera.image_count)
  return [...totals.entries()]
    .filter(([, count]) => count > 0)
    .map(([group, count]) => ({ group, label: GROUP_LABELS[group], count }))
}

import type { ReactNode } from 'react'
import {
  IconAssistant,
  IconExplorer,
  IconMissionControl,
  IconPerception,
  IconReplay,
  IconTerrain,
} from '../design-system/icons'

export interface ModuleDef {
  id: string
  path: string
  label: string
  short: string
  icon: ReactNode
  phase: number
  /** Built and usable in the current release. */
  available: boolean
  description: string
  plan: string[]
}

export const MODULES: ModuleDef[] = [
  {
    id: 'mission-control',
    path: '/',
    label: 'Mission Control',
    short: 'Control',
    icon: <IconMissionControl />,
    phase: 1,
    available: true,
    description: 'Overview of the latest real observations, rover localization and system state.',
    plan: [],
  },
  {
    id: 'explorer',
    path: '/explorer',
    label: 'Explorer',
    short: 'Explorer',
    icon: <IconExplorer />,
    phase: 2,
    available: true,
    description: 'Browse, filter and compare real Perseverance images with full provenance.',
    plan: [],
  },
  {
    id: 'perception',
    path: '/perception',
    label: 'Perception',
    short: 'Vision',
    icon: <IconPerception />,
    phase: 3,
    available: false,
    description: 'Computer-vision experiments on raw imagery, with every result labelled by method.',
    plan: [
      'Enhancement and filtering pipeline (CLAHE, denoising, edge detection)',
      'Rock / obstacle candidate detection drawn over the original image',
      'Terrain segmentation (classical first; optional model trained on AI4Mars)',
      'Benchmarks comparing algorithms, with honest limitations',
    ],
  },
  {
    id: 'terrain',
    path: '/terrain',
    label: 'Terrain & Navigation',
    short: 'Terrain',
    icon: <IconTerrain />,
    phase: 4,
    available: false,
    description: 'Cost maps on real orbital elevation data and explainable route planning.',
    plan: [
      'Real 1 m/px orbital DEM of the traverse area (PDS PLACES), slope and roughness layers',
      'Cost maps and risk classes with clearly stated assumptions',
      'A*, Dijkstra, Theta* and RRT* planners compared side by side',
      'Planned routes overlaid on the real Perseverance traverse, with cost breakdowns',
    ],
  },
  {
    id: 'replay',
    path: '/replay',
    label: 'Mission Replay',
    short: 'Replay',
    icon: <IconReplay />,
    phase: 5,
    available: false,
    description: 'Timeline of real observations, official videos and reconstructed frame sequences.',
    plan: [
      'Sol-by-sol timeline linking images to real localizations',
      'Official NASA videos (EDL landing, Ingenuity) from the NASA Image Library',
      'Frame-sequence playback rebuilt from raw images — always labelled as reconstructed',
    ],
  },
  {
    id: 'assistant',
    path: '/assistant',
    label: 'Assistant',
    short: 'Assist',
    icon: <IconAssistant />,
    phase: 5,
    available: false,
    description: 'Optional AI assistant with read-only access to mission context. Never drives the rover.',
    plan: [
      'Explain selected images, perception results and route decisions',
      'Generate concise mission reports from stored data',
      'Optional: needs an API key; the app works fully without it',
    ],
  },
]

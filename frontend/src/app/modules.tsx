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
    available: true,
    description: 'Computer-vision experiments on raw imagery, with every result labelled by method.',
    plan: [],
  },
  {
    id: 'terrain',
    path: '/terrain',
    label: 'Terrain & Navigation',
    short: 'Terrain',
    icon: <IconTerrain />,
    phase: 4,
    available: true,
    description: 'Cost maps on real orbital elevation data and explainable route planning.',
    plan: [],
  },
  {
    id: 'replay',
    path: '/replay',
    label: 'Mission Replay',
    short: 'Replay',
    icon: <IconReplay />,
    phase: 5,
    available: true,
    description: 'Sol-by-sol timeline of real images and drives, reconstructed frame sequences and official NASA videos.',
    plan: [],
  },
  {
    id: 'assistant',
    path: '/assistant',
    label: 'Assistant',
    short: 'Assist',
    icon: <IconAssistant />,
    phase: 5,
    available: true,
    description: 'Optional AI assistant (your Anthropic API key) with read-only access to mission data. Never drives the rover.',
    plan: [],
  },
]

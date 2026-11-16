// Hand-drawn 20×20 line icons (1.5px stroke, currentColor). Decorative: always aria-hidden.
import type { ReactNode } from 'react'

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  )
}

export const IconMissionControl = () => (
  <Icon>
    <rect x="2.5" y="3.5" width="15" height="10" rx="1" />
    <path d="M7 17h6M10 13.5V17M5.5 10l2.5-2.5 2 2 4-4" />
  </Icon>
)

export const IconExplorer = () => (
  <Icon>
    <rect x="2.5" y="2.5" width="6.5" height="6.5" rx="1" />
    <rect x="11" y="2.5" width="6.5" height="6.5" rx="1" />
    <rect x="2.5" y="11" width="6.5" height="6.5" rx="1" />
    <circle cx="14.25" cy="14.25" r="2.75" />
    <path d="M16.3 16.3l1.7 1.7" />
  </Icon>
)

export const IconPerception = () => (
  <Icon>
    <path d="M2.5 6V3.5a1 1 0 0 1 1-1H6M14 2.5h2.5a1 1 0 0 1 1 1V6M17.5 14v2.5a1 1 0 0 1-1 1H14M6 17.5H3.5a1 1 0 0 1-1-1V14" />
    <path d="M6.5 12.5l2-3 2 2 3-4" />
  </Icon>
)

export const IconTerrain = () => (
  <Icon>
    <path d="M2 16l5-8 3 4 2-3 6 7z" />
    <path d="M4 5.5c1.5-1 3-1 4.5 0s3 1 4.5 0" strokeDasharray="1.5 2" />
  </Icon>
)

export const IconReplay = () => (
  <Icon>
    <circle cx="10" cy="10" r="7.5" />
    <path d="M8.5 7l4 3-4 3z" />
  </Icon>
)

export const IconAssistant = () => (
  <Icon>
    <path d="M3.5 4.5h13v8.5h-7l-3.5 3v-3H3.5z" />
    <path d="M7 8.5h6M7 11h3.5" />
  </Icon>
)

export const IconExternal = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">
    <path d="M5 2.5H2.5v7h7V7M7 2.5h2.5V5M9.5 2.5L5.5 6.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

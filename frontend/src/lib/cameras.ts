/**
 * Compact instrument labels for tight UI (thumbnails, chips). The full id stays in tooltips
 * and the inspector. Unknown instruments fall back to the id with spaces.
 */
const SHORT: Record<string, string> = {
  NAVCAM_LEFT: 'NAVCAM L',
  NAVCAM_RIGHT: 'NAVCAM R',
  FRONT_HAZCAM_LEFT_A: 'F-HAZ L·A',
  FRONT_HAZCAM_LEFT_B: 'F-HAZ L·B',
  FRONT_HAZCAM_RIGHT_A: 'F-HAZ R·A',
  FRONT_HAZCAM_RIGHT_B: 'F-HAZ R·B',
  REAR_HAZCAM_LEFT: 'R-HAZ L',
  REAR_HAZCAM_RIGHT: 'R-HAZ R',
  MCZ_LEFT: 'MCZ L',
  MCZ_RIGHT: 'MCZ R',
  SUPERCAM_RMI: 'SCAM RMI',
  SHERLOC_WATSON: 'WATSON',
  SHERLOC_ACI: 'SHERLOC ACI',
  PIXL_MCC: 'PIXL MCC',
}

export function shortInstrument(instrument: string): string {
  return SHORT[instrument] ?? instrument.replace(/_/g, ' ')
}

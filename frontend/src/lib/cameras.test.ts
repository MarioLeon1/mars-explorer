import { describe, expect, it } from 'vitest'
import { shortInstrument } from './cameras'

describe('shortInstrument', () => {
  it('abbreviates long instrument ids and keeps unknown ones readable', () => {
    expect(shortInstrument('FRONT_HAZCAM_LEFT_A')).toBe('F-HAZ L·A')
    expect(shortInstrument('MCZ_RIGHT')).toBe('MCZ R')
    expect(shortInstrument('NEW_CAMERA')).toBe('NEW CAMERA')
  })
})

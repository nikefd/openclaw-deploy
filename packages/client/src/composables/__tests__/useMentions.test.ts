import { describe, it, expect } from 'vitest'
import { scanMention } from '@/composables/useMentions'

describe('useMentions / scanMention', () => {
  it('returns trigger=true for "@" alone', () => {
    const r = scanMention('hello @', 7)
    expect(r.trigger).toBe(true)
    expect(r.query).toBe('')
    expect(r.atIndex).toBe(6)
  })

  it('captures the in-progress query', () => {
    const r = scanMention('hello @gou', 10)
    expect(r.trigger).toBe(true)
    expect(r.query).toBe('gou')
  })

  it('disengages once whitespace appears after the @', () => {
    const r = scanMention('hello @gou ', 11)
    expect(r.trigger).toBe(false)
  })

  it('requires the @ to be preceded by whitespace or start-of-string', () => {
    const a = scanMention('hello@nope', 10)
    expect(a.trigger).toBe(false)
    const b = scanMention('@start', 6)
    expect(b.trigger).toBe(true)
    expect(b.query).toBe('start')
  })

  it('respects the cursor position (text after cursor is ignored)', () => {
    const r = scanMention('foo @bar baz', 5) // cursor right after the @
    expect(r.trigger).toBe(true)
    expect(r.query).toBe('')
  })

  it('handles no @ at all', () => {
    const r = scanMention('hello world', 11)
    expect(r.trigger).toBe(false)
    expect(r.atIndex).toBe(-1)
  })
})

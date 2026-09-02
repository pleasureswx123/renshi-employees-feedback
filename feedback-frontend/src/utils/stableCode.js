let sequence = 0

export function createStableCode(prefix) {
  sequence += 1
  const randomPart = globalThis.crypto?.randomUUID?.().replaceAll('-', '')
  return `${prefix}_${randomPart || `${Date.now()}_${sequence}`}`
}

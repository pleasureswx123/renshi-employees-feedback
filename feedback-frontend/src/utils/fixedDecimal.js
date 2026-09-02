export const DECIMAL_SCALE = 4
export const DECIMAL_FACTOR = 10 ** DECIMAL_SCALE

function decimalText(value) {
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new TypeError('十进制数必须是有限数字')
    return value.toFixed(DECIMAL_SCALE)
  }
  const text = String(value ?? '').trim()
  if (!text) throw new TypeError('十进制数不能为空')
  return text
}

export function toScaledInteger(value) {
  const text = decimalText(value)
  const match = /^([+-]?)(\d+)(?:\.(\d+))?$/.exec(text)
  if (!match) throw new TypeError(`非法十进制数：${text}`)
  const fraction = match[3] || ''
  if (fraction.length > DECIMAL_SCALE && /[1-9]/.test(fraction.slice(DECIMAL_SCALE))) {
    throw new RangeError('正式小数最多保留4位')
  }
  const paddedFraction = fraction.slice(0, DECIMAL_SCALE).padEnd(DECIMAL_SCALE, '0')
  const scaled = Number(match[2]) * DECIMAL_FACTOR + Number(paddedFraction)
  if (!Number.isSafeInteger(scaled)) throw new RangeError('十进制数超出安全范围')
  return match[1] === '-' ? -scaled : scaled
}

export function fromScaledInteger(value, decimalPlaces = DECIMAL_SCALE) {
  if (!Number.isSafeInteger(value)) throw new TypeError('定点值必须是安全整数')
  if (!Number.isInteger(decimalPlaces) || decimalPlaces < 0 || decimalPlaces > DECIMAL_SCALE) {
    throw new RangeError('小数位数必须在0至4之间')
  }
  const sign = value < 0 ? '-' : ''
  const absolute = Math.abs(value)
  const integerPart = Math.floor(absolute / DECIMAL_FACTOR)
  if (decimalPlaces === 0) return `${sign}${integerPart}`
  const fraction = String(absolute % DECIMAL_FACTOR).padStart(DECIMAL_SCALE, '0')
  return `${sign}${integerPart}.${fraction.slice(0, decimalPlaces)}`
}

export function normalizeDecimal(value) {
  return fromScaledInteger(toScaledInteger(value))
}

export function decimalToNumber(value) {
  return toScaledInteger(value) / DECIMAL_FACTOR
}

export function sumDecimals(values) {
  return fromScaledInteger(values.reduce((total, value) => total + toScaledInteger(value), 0))
}

export function compareDecimals(left, right) {
  return Math.sign(toScaledInteger(left) - toScaledInteger(right))
}

export function isDecimalOnStep(value, minimum, step) {
  const stepValue = toScaledInteger(step)
  return stepValue > 0 && (toScaledInteger(value) - toScaledInteger(minimum)) % stepValue === 0
}

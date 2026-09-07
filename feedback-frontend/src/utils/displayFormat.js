// 仅整理显示格式，不推断或转换服务端未声明的时区。
export function formatDateTime(value) {
  if (!value) return '—'
  const text = String(value)
  const match = text.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)(?:\.\d+)?(Z|[+-]\d{2}:\d{2})?$/)
  return match ? `${match[1]} ${match[2]}${match[3] ? ` ${match[3]}` : ''}` : text
}

export function formatTableDate(_row, _column, value) {
  return formatDateTime(value)
}

// 只删除十进制末尾的零，不转换为浮点数、不舍入，适用于原始题分及公式。
export function trimDecimalZeros(value) {
  if (value == null) return '—'
  return String(value).replace(/\d+\.\d+/g, decimal => decimal.replace(/0+$/, '').replace(/\.$/, ''))
}

// 公式展示最多两位小数；用十进制字符串舍入，避免长精度值经过浮点数转换。
export function formatFormulaPreview(value) {
  if (value == null) return '—'
  return String(value).replace(/-?\d+\.\d+/g, decimal => {
    const negative = decimal.startsWith('-')
    const [integer, fraction] = decimal.replace(/^-/, '').split('.')
    let scaled = BigInt(integer + fraction.padEnd(2, '0').slice(0, 2))
    if (fraction.length > 2 && fraction[2] >= '5') scaled += 1n
    const digits = scaled.toString().padStart(3, '0')
    return trimDecimalZeros(`${negative && scaled !== 0n ? '-' : ''}${digits.slice(0, -2)}.${digits.slice(-2)}`)
  })
}

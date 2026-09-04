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

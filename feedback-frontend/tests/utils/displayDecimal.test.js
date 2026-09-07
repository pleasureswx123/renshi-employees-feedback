import { expect, it } from 'vitest'
import { trimDecimalZeros, formatFormulaPreview } from '@/utils/displayFormat'

it('原始题分和公式只去除无意义的零，保留真实小数和全部精度', () => {
  expect(trimDecimalZeros('3.0000')).toBe('3')
  expect(trimDecimalZeros('0.0000')).toBe('0')
  expect(trimDecimalZeros('2.5000')).toBe('2.5')
  expect(trimDecimalZeros('3.0000 + 2.5000 = 5.5000')).toBe('3 + 2.5 = 5.5')
  expect(trimDecimalZeros('53.211009174311926605504587155963302752293577981651')).toBe('53.211009174311926605504587155963302752293577981651')
  expect(trimDecimalZeros(null)).toBe('—')
})

it('公式预览限制两位小数，正确处理进位且不丢失大整数精度', () => {
  expect(formatFormulaPreview('53.211009174311926605504587155963302752293577981651 ÷ 1')).toBe('53.21 ÷ 1')
  expect(formatFormulaPreview('9.995 + 3.0000 + 2.5000')).toBe('10 + 3 + 2.5')
  expect(formatFormulaPreview('9007199254740993.125')).toBe('9007199254740993.13')
  expect(formatFormulaPreview('-1.005')).toBe('-1.01')
})

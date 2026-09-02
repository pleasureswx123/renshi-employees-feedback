import { describe, expect, it } from 'vitest'

import {
  compareDecimals,
  fromScaledInteger,
  isDecimalOnStep,
  normalizeDecimal,
  sumDecimals,
  toScaledInteger
} from '@/utils/fixedDecimal'

describe('正式分值定点数工具', () => {
  it('使用四位定点整数规避0.1加0.2的浮点误差', () => {
    expect(toScaledInteger('0.1000')).toBe(1000)
    expect(sumDecimals(['0.1000', '0.2000'])).toBe('0.3000')
    expect(fromScaledInteger(123456)).toBe('12.3456')
    expect(normalizeDecimal(5)).toBe('5.0000')
  })

  it('精确比较并判断滑动步长', () => {
    expect(compareDecimals('10.0000', '9.9999')).toBe(1)
    expect(isDecimalOnStep('0.3000', '0.1000', '0.1000')).toBe(true)
    expect(isDecimalOnStep('0.3500', '0.1000', '0.1000')).toBe(false)
  })

  it('拒绝超过四位的有效小数和非法文本', () => {
    expect(() => toScaledInteger('1.00001')).toThrow('最多保留4位')
    expect(() => toScaledInteger('NaN')).toThrow('非法十进制数')
  })
})

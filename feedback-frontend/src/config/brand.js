// 两端使用同一品牌，资源在各自工程内独立交付。
export const brand = Object.freeze({
  name: '同见',
  edition: '评价平台',
  title: import.meta.env.VITE_APP_TITLE || '同见 · 评价平台',
  description: '员工反馈与 360° 评价',
  tagline: '多方反馈，看见成长',
  logo: `${import.meta.env.BASE_URL}brand-mark.svg`,
  companyName: 'LAPUTTA',
  companyLogo: `${import.meta.env.BASE_URL}company_logo.svg?v=laputta-1`
})

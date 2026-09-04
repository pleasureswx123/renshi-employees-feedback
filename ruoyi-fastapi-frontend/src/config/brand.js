// 与评价平台共用品牌含义，资源与构建在管理端独立维护。
export const brand = Object.freeze({
  name: '同见',
  edition: '管理中心',
  title: import.meta.env.VITE_APP_TITLE || '同见 · 管理中心',
  description: '组织、账号与权限管理',
  tagline: '多方反馈，看见成长',
  logo: `${import.meta.env.BASE_URL}brand-mark.svg`,
  companyName: 'LAPUTTA',
  companyLogo: `${import.meta.env.BASE_URL}company_logo.svg?v=laputta-1`
})

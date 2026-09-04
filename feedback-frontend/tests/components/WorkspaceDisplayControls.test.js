import ElementPlus, { ElMessage } from 'element-plus'
import { createPinia, disposePinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import WorkspaceDisplayControls from '@/components/WorkspaceDisplayControls.vue'
import { useWorkspaceUiStore } from '@/stores/workspaceUi'
import { THEME_STORAGE_KEY } from '@/utils/appearance'

let wrapper
let pinia
let fullscreenElement
let enterFullscreen
let exitFullscreen
const initialDescriptors = [
  [document, 'fullscreenEnabled'], [document, 'fullscreenElement'], [document, 'exitFullscreen'],
  [document.documentElement, 'requestFullscreen']
].map(([object, key]) => ({ object, key, descriptor: Object.getOwnPropertyDescriptor(object, key) }))

async function open() {
  wrapper = mount(WorkspaceDisplayControls, { global: { plugins: [pinia, ElementPlus] } })
  await flushPromises()
  return wrapper
}
function button(name) { return wrapper.findAll('button').find(item => item.attributes('aria-label') === name) }
function setFullscreen(element) {
  fullscreenElement = element
  document.dispatchEvent(new Event('fullscreenchange'))
}

describe('全屏与主题显示设置', () => {
  beforeEach(() => {
    localStorage.clear()
    pinia = createPinia()
    setActivePinia(pinia)
    fullscreenElement = null
    enterFullscreen = vi.fn(async () => setFullscreen(document.documentElement))
    exitFullscreen = vi.fn(async () => setFullscreen(null))
    Object.defineProperties(document, {
      fullscreenEnabled: { configurable: true, value: true },
      fullscreenElement: { configurable: true, get: () => fullscreenElement },
      exitFullscreen: { configurable: true, value: exitFullscreen }
    })
    Object.defineProperty(document.documentElement, 'requestFullscreen', { configurable: true, value: enterFullscreen })
  })
  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    disposePinia(pinia)
    document.documentElement.classList.remove('dark')
    document.documentElement.style.colorScheme = ''
    localStorage.clear()
    for (const { object, key, descriptor } of initialDescriptors) {
      if (descriptor) Object.defineProperty(object, key, descriptor)
      else delete object[key]
    }
  })

  it('点击切换主题，重建Store恢复偏好，返回浅色时移除全局暗色状态', async () => {
    await open()
    await button('切换到深色模式').trigger('click')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(document.documentElement.style.colorScheme).toBe('dark')
    expect(button('切换到浅色模式').attributes('aria-pressed')).toBe('true')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
    wrapper.unmount()
    disposePinia(pinia)
    pinia = createPinia()
    setActivePinia(pinia)
    await open()
    expect(button('切换到浅色模式')).toBeDefined()
    await button('切换到浅色模式').trigger('click')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
  })

  it('浏览器禁止本地存储时仍可完成当前主题切换', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
    await open()
    await button('切换到深色模式').trigger('click')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(useWorkspaceUiStore().isDark).toBe(true)
  })

  it('其他标签页更改主题时同步，Store销毁后解除监听', () => {
    const ui = useWorkspaceUiStore()
    localStorage.setItem(THEME_STORAGE_KEY, 'dark')
    window.dispatchEvent(new StorageEvent('storage', { key: 'unrelated' }))
    expect(ui.isDark).toBe(false)
    window.dispatchEvent(new StorageEvent('storage', { key: THEME_STORAGE_KEY }))
    expect(ui.isDark).toBe(true)
    disposePinia(pinia)
    localStorage.setItem(THEME_STORAGE_KEY, 'light')
    window.dispatchEvent(new StorageEvent('storage', { key: THEME_STORAGE_KEY }))
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('真实状态事件驱动进入和退出图标，并能感知Esc退出', async () => {
    await open()
    await button('进入全屏').trigger('click')
    await flushPromises()
    expect(enterFullscreen).toHaveBeenCalledTimes(1)
    expect(button('退出全屏').attributes('aria-pressed')).toBe('true')
    setFullscreen(null)
    await flushPromises()
    expect(button('进入全屏')).toBeDefined()
    await button('进入全屏').trigger('click')
    await flushPromises()
    await button('退出全屏').trigger('click')
    await flushPromises()
    expect(exitFullscreen).toHaveBeenCalledTimes(1)
    expect(button('进入全屏')).toBeDefined()
  })

  it('全屏请求期间防重复，拒绝后恢复按钮并反馈错误', async () => {
    let rejectRequest
    enterFullscreen.mockImplementation(() => new Promise((_resolve, reject) => { rejectRequest = reject }))
    const warning = vi.spyOn(ElMessage, 'warning').mockImplementation(() => {})
    await open()
    await button('进入全屏').trigger('click')
    expect(button('进入全屏').element.disabled).toBe(true)
    await button('进入全屏').trigger('click')
    expect(enterFullscreen).toHaveBeenCalledTimes(1)
    rejectRequest(new Error('denied'))
    await flushPromises()
    expect(button('进入全屏').element.disabled).toBe(false)
    expect(button('退出全屏')).toBeUndefined()
    expect(warning).toHaveBeenCalledWith('全屏切换失败，请重试或检查浏览器是否允许全屏')
  })

  it('不支持全屏时禁用入口，但主题切换仍可用', async () => {
    Object.defineProperty(document, 'fullscreenEnabled', { configurable: true, value: false })
    await open()
    expect(button('当前浏览器不支持全屏').element.disabled).toBe(true)
    await button('当前浏览器不支持全屏').trigger('click')
    expect(enterFullscreen).not.toHaveBeenCalled()
    await button('切换到深色模式').trigger('click')
    expect(useWorkspaceUiStore().isDark).toBe(true)
  })
})

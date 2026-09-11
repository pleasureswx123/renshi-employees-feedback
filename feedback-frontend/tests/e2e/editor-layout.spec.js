import { expect, test } from '@playwright/test'

// 使用隔离的长问卷检验布局，不修改开发库或用户当前草稿。
function longDraft() {
  return {
    projectId: 101, projectName: '跨部门协作与管理能力评价项目'.repeat(5), projectStatus: 'PREPARING',
    versionId: 201, versionNo: 1, versionStatus: 'DRAFT', lockVersion: 0,
    title: '长问卷布局验证', description: '', descriptionDoc: { type: 'doc', content: [{ type: 'paragraph' }] },
    settings: {}, indicators: [], validationIssues: [], isPublishReady: false,
    pages: Array.from({ length: 12 }, (_, page) => ({
      pageId: page + 1, pageCode: `P${page + 1}`, pageTitle: `第${page + 1}页`, sortOrder: page + 1,
      questions: Array.from({ length: 10 }, (_, question) => ({
        questionId: page * 10 + question + 1, questionCode: `Q${page + 1}_${question + 1}`,
        questionType: 'TEXT', title: `问题${question + 1}：${'请描述跨部门协作中值得保持和改进的做法。'.repeat(4)}`,
        description: '', isRequired: true, isScored: false, sortOrder: question + 1,
        minScore: null, maxScore: null, decimalPlaces: 0, config: { maxLength: 1000 }, options: []
      }))
    }))
  }
}

for (const viewport of [{ width: 1466, height: 986 }, { width: 1236, height: 720 }]) {
  test(`长问卷各栏独立滚动且题型入口始终可见 ${viewport.width}x${viewport.height}`, async ({ page, context }, testInfo) => {
    await page.setViewportSize(viewport)
    await context.addCookies([{ name: 'Feedback-Token', value: 'layout-test-token', url: 'http://127.0.0.1:5176' }])
    let saves = 0
    let persistedDraft = longDraft()
    await page.route('**/dev-api/**', route => {
      const path = new URL(route.request().url()).pathname.replace('/dev-api', '')
      if (route.request().method() !== 'GET') saves += 1
      if (path === '/transport/crypto/frontend-config') return route.fulfill({ json: { code: 200, data: {
        transportCryptoEnabled: false, transportCryptoMode: 'off', transportCryptoActive: false,
        configExpireAt: Math.floor(Date.now() / 1000) + 300
      } } })
      if (path === '/getInfo') return route.fulfill({ json: {
        code: 200, user: { userId: 2, userName: '布局测试用户' }, roles: ['feedback_hr'],
        permissions: ['feedback:project:list', 'feedback:questionnaire:edit', 'feedback:participant:manage']
      } })
      if (path === '/feedback/projects/101/questionnaire-draft') {
        if (route.request().method() === 'PUT') persistedDraft = { ...persistedDraft, ...route.request().postDataJSON(), lockVersion: persistedDraft.lockVersion + 1 }
        return route.fulfill({ json: { code: 200, data: persistedDraft } })
      }
      return route.fulfill({ status: 404, json: { code: 404, msg: '未匹配测试接口' } })
    })
    await page.goto('/hr/projects/101/editor')
    await expect(page.locator('.outline-page-group')).toHaveCount(12)
    const typePanel = page.locator('.type-panel')
    const assertTypePanelVisible = async () => {
      const box = await typePanel.boundingBox()
      expect(box.y).toBeGreaterThanOrEqual(0)
      expect(box.y + box.height).toBeLessThanOrEqual(viewport.height)
      await expect(typePanel.getByRole('button', { name: /^问答题/ })).toBeInViewport()
    }
    await assertTypePanelVisible()
    const editorHeader = await page.locator('.editor-header').boundingBox()
    expect(editorHeader.height).toBeLessThanOrEqual(64)
    expect(editorHeader.x + editorHeader.width).toBeLessThanOrEqual(viewport.width)
    await expect(page.getByRole('button', { name: '第1步：编辑问卷', exact: true })).toHaveAttribute('aria-current', 'step')
    await expect(page.getByLabel('评价准备流程')).toContainText('检查并发布')
    const typeTop = (await typePanel.boundingBox()).y
    const assertEditorFrameStable = async () => {
      const frame = await page.evaluate(() => {
        const header = document.querySelector('.workspace-header').getBoundingClientRect()
        const grid = document.querySelector('.editor-grid').getBoundingClientRect()
        return {
          headerTop: header.top,
          bottomGap: window.innerHeight - grid.bottom,
          documentOverflow: document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight,
          outerScroll: ['.workspace-layout', '.workspace-main'].map(selector => document.querySelector(selector).scrollTop)
        }
      })
      expect(frame.headerTop).toBe(0)
      expect(frame.bottomGap).toBeLessThanOrEqual(21)
      expect(frame.documentOverflow).toBeLessThanOrEqual(1)
      expect(frame.outerScroll).toEqual([0, 0])
    }
    await page.locator('.outline-pages').evaluate(el => { el.scrollTop = el.scrollHeight })
    await expect(page.locator('.outline-question').last()).toBeInViewport()
    await assertTypePanelVisible()
    expect((await typePanel.boundingBox()).y).toBe(typeTop)

    await page.locator('.canvas-panel').evaluate(el => { el.scrollTop = el.scrollHeight })
    await assertTypePanelVisible()
    await expect(page.getByRole('button', { name: '保存草稿', exact: true })).toBeInViewport()
    await typePanel.getByRole('button', { name: /^数字输入/ }).click()
    await expect(page.locator('.outline-question.active')).toContainText('数字输入')
    await expect(page.locator('.question-card.active')).toBeInViewport()
    await page.screenshot({ path: testInfo.outputPath('editor-properties.png') })
    await assertEditorFrameStable()

    // 校验定位到长问卷底部的空题时，外层工作台不能被连带滚动。
    await page.getByRole('button', { name: '保存草稿', exact: true }).click()
    await expect(page.locator('.question-card.active .title-field textarea')).toBeFocused()
    await expect(page.locator('.question-card.active')).toContainText('请填写题目内容')
    await page.screenshot({ path: testInfo.outputPath('editor-validation.png') })
    await assertEditorFrameStable()

    await page.locator('.question-card.active .title-field textarea').fill('请为跨部门协作评分')
    await page.getByRole('tab', { name: '实时预览', exact: true }).click()
    const toolbar = page.locator('.live-preview-toolbar')
    await expect(toolbar).toContainText('第 1 / 12 页')
    const rightPanel = await page.locator('.right-panel').boundingBox()
    expect(rightPanel.x + rightPanel.width).toBeLessThanOrEqual(viewport.width)
    await expect(page.getByText('修改即时同步，试填内容不会保存。', { exact: true })).toHaveCount(0)
    const status = await toolbar.locator('.preview-page-status').boundingBox()
    const pagination = await toolbar.locator('.live-preview-pagination').boundingBox()
    const reset = await toolbar.getByRole('button', { name: '重新试填' }).boundingBox()
    expect(Math.abs(status.y + status.height / 2 - pagination.y - pagination.height / 2)).toBeLessThan(2)
    expect(Math.abs(reset.y + reset.height / 2 - pagination.y - pagination.height / 2)).toBeLessThan(2)
    expect(pagination.x + pagination.width).toBeLessThanOrEqual(reset.x)
    await toolbar.locator('.live-preview-pagination').getByText('2', { exact: true }).click()
    await expect(toolbar).toContainText('第 2 / 12 页')
    await page.locator('.right-panel .el-tabs__content').evaluate(el => { el.scrollTop = el.scrollHeight })
    await expect(toolbar.getByRole('button', { name: '重新试填' })).toBeInViewport()
    await assertTypePanelVisible()
    await page.screenshot({ path: testInfo.outputPath('editor-preview.png') })

    await page.getByRole('button', { name: '下一步：配置指标与权重', exact: true }).click()
    await expect(page.getByRole('tab', { name: '评价指标', exact: true })).toHaveAttribute('aria-selected', 'true')
    await expect(page.locator('.indicator-step-notice')).toContainText('还有1道计分题未绑定指标')
    await page.getByRole('button', { name: '下一步：评价谁', exact: true }).click()
    await expect(page).toHaveURL(/\/hr\/projects\/101\/editor$/)
    expect(saves).toBe(1)
    await page.getByRole('button', { name: '增加指标', exact: true }).click()
    await page.getByRole('button', { name: '增加指标', exact: true }).click()
    const indicatorCards = page.locator('.indicator-card')
    await expect(indicatorCards).toHaveCount(2)
    for (const card of await indicatorCards.all()) {
      await expect(card.getByLabel('权重（%）')).toHaveValue('0')
      const box = await card.boundingBox()
      expect(box.height).toBeLessThan(250)
      for (const control of await card.locator('.el-input, .el-input-number, .el-textarea, .el-select').all()) {
        const controlBox = await control.boundingBox()
        expect(controlBox.x).toBeGreaterThanOrEqual(box.x)
        expect(controlBox.x + controlBox.width).toBeLessThanOrEqual(box.x + box.width)
      }
    }
    await expect(page.getByRole('button', { name: '上移指标 1', exact: true })).toBeDisabled()
    await expect(page.getByRole('button', { name: '下移指标 2', exact: true })).toBeDisabled()
    await page.getByRole('button', { name: '下移指标 1', exact: true }).click()
    await expect(indicatorCards.first().getByLabel('指标名称')).toHaveValue('指标2')
    await page.getByRole('button', { name: '上移指标 2', exact: true }).click()
    await expect(indicatorCards.first().getByLabel('指标名称')).toHaveValue('指标1')
    await indicatorCards.first().getByLabel('指标名称').fill('跨部门协作与沟通能力'.repeat(5))
    await indicatorCards.first().getByLabel('指标说明').fill('结合实际协作表现，说明此指标包含的评价范围。'.repeat(8))
    await assertEditorFrameStable()
    await page.mouse.move(0, 0)
    await expect(page.getByRole('tooltip')).toHaveCount(0)
    await page.screenshot({ path: testInfo.outputPath('editor-indicators.png') })

    // 指标步骤后又新增空题，主操作应先回到完善问卷，已有指标不能丢失。
    await typePanel.getByRole('button', { name: /^数字输入/ }).click()
    await expect(page.getByRole('tab', { name: '题目属性', exact: true })).toHaveAttribute('aria-selected', 'true')
    await expect(page.getByRole('button', { name: '完善问卷', exact: true })).toBeVisible()
    await page.getByRole('tab', { name: '评价指标', exact: true }).click()
    await expect(page.getByRole('button', { name: '下一步：评价谁', exact: true })).toHaveCount(0)
    await expect(page.locator('.indicator-step-notice')).toContainText('已有指标配置会保留')
    await page.getByRole('button', { name: '完善问卷', exact: true }).click()
    const addedTitle = page.locator('.question-card.active .title-field textarea')
    await expect(addedTitle).toBeFocused()
    const longQuestionTitle = '指标配置后追加的评分题：请评价跨部门协作中的实际表现。'.repeat(12)
    await addedTitle.fill(longQuestionTitle)
    await page.getByRole('button', { name: '下一步：配置指标与权重', exact: true }).click()
    await expect(page.locator('.indicator-step-notice')).toContainText('还有2道计分题未绑定指标')
    await expect(indicatorCards).toHaveCount(2)
    await expect(indicatorCards.first().getByLabel('指标名称')).toHaveValue('跨部门协作与沟通能力'.repeat(5))
    await assertEditorFrameStable()
    const pendingItems = page.locator('.unbound-item')
    await expect(pendingItems).toHaveCount(2)
    await expect(pendingItems.first()).toContainText('第 11 题')
    await expect(pendingItems.first()).toContainText('第 1 页')
    await expect(pendingItems.last()).toContainText('第 22 题')
    await expect(pendingItems.last()).toContainText('第 2 页')
    await pendingItems.first().getByRole('combobox').click()
    await page.getByRole('option', { name: '跨部门协作与沟通能力'.repeat(5), exact: true }).click()
    await expect(pendingItems).toHaveCount(1)
    await pendingItems.first().getByRole('button', { name: /^定位第/ }).click()
    await expect(page.getByRole('tab', { name: '评价指标', exact: true })).toHaveAttribute('aria-selected', 'true')
    await expect(page.locator('.question-card.active .title-field textarea')).toHaveValue(longQuestionTitle)
    const pendingPanel = await page.locator('.unbound-panel').boundingBox()
    const pendingTitle = await page.locator('.unbound-question-link').boundingBox()
    expect(pendingTitle.x + pendingTitle.width).toBeLessThanOrEqual(pendingPanel.x + pendingPanel.width)
    expect(pendingTitle.height).toBeLessThan(62)
    await page.screenshot({ path: testInfo.outputPath('editor-unbound.png') })
    await pendingItems.first().getByRole('combobox').click()
    await page.getByRole('option', { name: '指标2', exact: true }).click()
    await expect(pendingItems).toHaveCount(0)
    await expect(page.locator('.binding-complete')).toHaveText('计分题已全部绑定')
    await page.getByRole('button', { name: '删除指标 2', exact: true }).click()
    await expect(indicatorCards).toHaveCount(1)
    await expect(pendingItems).toHaveCount(1)
    await expect(pendingItems.first()).toContainText(longQuestionTitle)

    await page.getByRole('button', { name: '用户菜单', exact: true }).click()
    await expect(page.getByRole('menuitem', { name: '退出登录', exact: true })).toBeVisible()
    await page.keyboard.press('Escape')
    expect(saves).toBe(2)
  })
}

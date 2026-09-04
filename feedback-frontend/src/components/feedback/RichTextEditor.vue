<script setup>
import BoldIcon from '@iconify-vue/lucide/bold'
import Heading2Icon from '@iconify-vue/lucide/heading-2'
import Heading3Icon from '@iconify-vue/lucide/heading-3'
import ItalicIcon from '@iconify-vue/lucide/italic'
import ListIcon from '@iconify-vue/lucide/list'
import ListOrderedIcon from '@iconify-vue/lucide/list-ordered'
import QuoteIcon from '@iconify-vue/lucide/quote'
import StrikethroughIcon from '@iconify-vue/lucide/strikethrough'
import UnderlineIcon from '@iconify-vue/lucide/underline'
import StarterKit from '@tiptap/starter-kit'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import { onBeforeUnmount, watch } from 'vue'

import { createRichTextDocument } from '@/utils/questionnaireDraft'

const props = defineProps({
  modelValue: { type: Object, default: null },
  readonly: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue'])

const editor = useEditor({
  content: props.modelValue || createRichTextDocument(),
  editable: !props.readonly,
  extensions: [
    StarterKit.configure({
      code: false,
      codeBlock: false,
      horizontalRule: false,
      link: false,
      heading: { levels: [2, 3] }
    })
  ],
  onUpdate: ({ editor: currentEditor }) => emit('update:modelValue', currentEditor.getJSON())
})

watch(
  () => props.readonly,
  value => editor.value?.setEditable(!value)
)

watch(
  () => props.modelValue,
  value => {
    if (!editor.value || !value) return
    if (JSON.stringify(editor.value.getJSON()) !== JSON.stringify(value)) {
      editor.value.commands.setContent(value, { emitUpdate: false })
    }
  },
  { deep: true }
)

onBeforeUnmount(() => editor.value?.destroy())
</script>

<template>
  <div :class="['rich-text', { 'is-readonly': readonly }]">
    <div v-if="editor && !readonly" class="rich-toolbar" role="group" aria-label="富文本工具栏">
      <!-- 提示响应悬浮与焦点，回车和空格交给按钮执行格式命令。 -->
      <div class="rich-tool-group" role="group" aria-label="文字格式">
        <el-tooltip content="加粗" placement="top" :show-after="300" :enterable="false" :trigger="['hover', 'focus']" :trigger-keys="[]">
          <el-button
            text class="rich-tool-button" aria-label="加粗"
            :aria-pressed="editor.isActive('bold')"
            :type="editor.isActive('bold') ? 'primary' : 'default'"
            @click="editor.chain().focus().toggleBold().run()"
          ><BoldIcon width="18" height="18" aria-hidden="true" /></el-button>
        </el-tooltip>
        <el-tooltip content="斜体" placement="top" :show-after="300" :enterable="false" :trigger="['hover', 'focus']" :trigger-keys="[]">
          <el-button
            text class="rich-tool-button" aria-label="斜体"
            :aria-pressed="editor.isActive('italic')"
            :type="editor.isActive('italic') ? 'primary' : 'default'"
            @click="editor.chain().focus().toggleItalic().run()"
          ><ItalicIcon width="18" height="18" aria-hidden="true" /></el-button>
        </el-tooltip>
        <el-tooltip content="下划线" placement="top" :show-after="300" :enterable="false" :trigger="['hover', 'focus']" :trigger-keys="[]">
          <el-button
            text class="rich-tool-button" aria-label="下划线"
            :aria-pressed="editor.isActive('underline')"
            :type="editor.isActive('underline') ? 'primary' : 'default'"
            @click="editor.chain().focus().toggleUnderline().run()"
          ><UnderlineIcon width="18" height="18" aria-hidden="true" /></el-button>
        </el-tooltip>
        <el-tooltip content="删除线" placement="top" :show-after="300" :enterable="false" :trigger="['hover', 'focus']" :trigger-keys="[]">
          <el-button
            text class="rich-tool-button" aria-label="删除线"
            :aria-pressed="editor.isActive('strike')"
            :type="editor.isActive('strike') ? 'primary' : 'default'"
            @click="editor.chain().focus().toggleStrike().run()"
          ><StrikethroughIcon width="18" height="18" aria-hidden="true" /></el-button>
        </el-tooltip>
      </div>
      <div class="rich-tool-group" role="group" aria-label="标题格式">
        <el-tooltip content="二级标题" placement="top" :show-after="300" :enterable="false" :trigger="['hover', 'focus']" :trigger-keys="[]">
          <el-button
            text class="rich-tool-button" aria-label="二级标题"
            :aria-pressed="editor.isActive('heading', { level: 2 })"
            :type="editor.isActive('heading', { level: 2 }) ? 'primary' : 'default'"
            @click="editor.chain().focus().toggleHeading({ level: 2 }).run()"
          ><Heading2Icon width="18" height="18" aria-hidden="true" /></el-button>
        </el-tooltip>
        <el-tooltip content="三级标题" placement="top" :show-after="300" :enterable="false" :trigger="['hover', 'focus']" :trigger-keys="[]">
          <el-button
            text class="rich-tool-button" aria-label="三级标题"
            :aria-pressed="editor.isActive('heading', { level: 3 })"
            :type="editor.isActive('heading', { level: 3 }) ? 'primary' : 'default'"
            @click="editor.chain().focus().toggleHeading({ level: 3 }).run()"
          ><Heading3Icon width="18" height="18" aria-hidden="true" /></el-button>
        </el-tooltip>
      </div>
      <div class="rich-tool-group" role="group" aria-label="列表与引用">
        <el-tooltip content="无序列表" placement="top" :show-after="300" :enterable="false" :trigger="['hover', 'focus']" :trigger-keys="[]">
          <el-button
            text class="rich-tool-button" aria-label="无序列表"
            :aria-pressed="editor.isActive('bulletList')"
            :type="editor.isActive('bulletList') ? 'primary' : 'default'"
            @click="editor.chain().focus().toggleBulletList().run()"
          ><ListIcon width="18" height="18" aria-hidden="true" /></el-button>
        </el-tooltip>
        <el-tooltip content="有序列表" placement="top" :show-after="300" :enterable="false" :trigger="['hover', 'focus']" :trigger-keys="[]">
          <el-button
            text class="rich-tool-button" aria-label="有序列表"
            :aria-pressed="editor.isActive('orderedList')"
            :type="editor.isActive('orderedList') ? 'primary' : 'default'"
            @click="editor.chain().focus().toggleOrderedList().run()"
          ><ListOrderedIcon width="18" height="18" aria-hidden="true" /></el-button>
        </el-tooltip>
        <el-tooltip content="引用段落" placement="top" :show-after="300" :enterable="false" :trigger="['hover', 'focus']" :trigger-keys="[]">
          <el-button
            text class="rich-tool-button" aria-label="引用"
            :aria-pressed="editor.isActive('blockquote')"
            :type="editor.isActive('blockquote') ? 'primary' : 'default'"
            @click="editor.chain().focus().toggleBlockquote().run()"
          ><QuoteIcon width="18" height="18" aria-hidden="true" /></el-button>
        </el-tooltip>
      </div>
    </div>
    <EditorContent v-if="editor" :editor="editor" />
  </div>
</template>

<style scoped>
.rich-text { width: 100%; min-width: 0; overflow: hidden; border: 1px solid var(--fb-border-strong, #dcdfe6); border-radius: 6px; background: var(--fb-surface, #fff); }
.rich-text.is-readonly { border: 0; background: transparent; }
.rich-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 6px 8px; border-bottom: 1px solid var(--fb-border, #e5e7eb); background: var(--fb-surface-muted, #f8fafc); }
.rich-tool-group { display: flex; flex-shrink: 0; align-items: center; gap: 2px; }
.rich-tool-group + .rich-tool-group { padding-left: 6px; border-left: 1px solid var(--fb-border, #dfe5ee); }
.rich-toolbar .rich-tool-button { width: 32px; height: 32px; margin: 0; padding: 0; border-radius: 4px; }
.rich-tool-button[aria-pressed="true"] { color: #409eff; background: var(--fb-primary-bg, #ecf5ff); }
.rich-tool-button:focus-visible { outline: 2px solid #409eff; outline-offset: 1px; }
/* 中文字体通常没有独立斜体字形，富文本需允许浏览器合成，覆盖全局禁用设置。 */
.rich-text:deep(.tiptap) { min-height: 120px; padding: 14px; outline: none; line-height: 1.7; font-synthesis: weight style; }
.rich-text.is-readonly:deep(.tiptap) { min-height: 0; padding: 0; }
.rich-text:deep(.tiptap em) { font-style: italic; }
.rich-text:deep(.tiptap blockquote) { margin: 12px 0; padding: 10px 14px; border-left: 3px solid var(--fb-primary-border, #a4c7fb); border-radius: 0 4px 4px 0; color: var(--fb-text-regular, #596579); background: var(--fb-primary-bg, #f5f8fd); }
.rich-text:deep(.tiptap blockquote:first-child) { margin-top: 0; }
.rich-text:deep(.tiptap blockquote:last-child) { margin-bottom: 0; }
.rich-text:deep(.tiptap p:first-child),
.rich-text :deep(.tiptap h2:first-child),
.rich-text :deep(.tiptap h3:first-child) { margin-top: 0; }
.rich-text:deep(.tiptap p:last-child) { margin-bottom: 0; }
</style>

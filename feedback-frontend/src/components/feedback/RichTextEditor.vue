<script setup>
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
    <div v-if="editor && !readonly" class="rich-toolbar" aria-label="富文本工具栏">
      <el-button
        size="small"
        :type="editor.isActive('bold') ? 'primary' : 'default'"
        @click="editor.chain().focus().toggleBold().run()"
      >加粗</el-button>
      <el-button
        size="small"
        :type="editor.isActive('italic') ? 'primary' : 'default'"
        @click="editor.chain().focus().toggleItalic().run()"
      >斜体</el-button>
      <el-button
        size="small"
        :type="editor.isActive('underline') ? 'primary' : 'default'"
        @click="editor.chain().focus().toggleUnderline().run()"
      >下划线</el-button>
      <el-button
        size="small"
        :type="editor.isActive('strike') ? 'primary' : 'default'"
        @click="editor.chain().focus().toggleStrike().run()"
      >删除线</el-button>
      <el-button
        size="small"
        :type="editor.isActive('heading', { level: 2 }) ? 'primary' : 'default'"
        @click="editor.chain().focus().toggleHeading({ level: 2 }).run()"
      >二级标题</el-button>
      <el-button
        size="small"
        :type="editor.isActive('heading', { level: 3 }) ? 'primary' : 'default'"
        @click="editor.chain().focus().toggleHeading({ level: 3 }).run()"
      >三级标题</el-button>
      <el-button
        size="small"
        :type="editor.isActive('bulletList') ? 'primary' : 'default'"
        @click="editor.chain().focus().toggleBulletList().run()"
      >无序列表</el-button>
      <el-button
        size="small"
        :type="editor.isActive('orderedList') ? 'primary' : 'default'"
        @click="editor.chain().focus().toggleOrderedList().run()"
      >有序列表</el-button>
      <el-button
        size="small"
        :type="editor.isActive('blockquote') ? 'primary' : 'default'"
        @click="editor.chain().focus().toggleBlockquote().run()"
      >引用</el-button>
    </div>
    <EditorContent v-if="editor" :editor="editor" />
  </div>
</template>

<style scoped>
.rich-text { overflow: hidden; border: 1px solid #dcdfe6; border-radius: 8px; background: #fff; }
.rich-text.is-readonly { border: 0; background: transparent; }
.rich-toolbar { display: flex; flex-wrap: wrap; gap: 6px; padding: 8px; border-bottom: 1px solid #e5e7eb; background: #f8fafc; }
.rich-toolbar :deep(.el-button + .el-button) { margin-left: 0; }
.rich-text :deep(.tiptap) { min-height: 120px; padding: 14px; outline: none; line-height: 1.7; }
.rich-text.is-readonly :deep(.tiptap) { min-height: 0; padding: 0; }
.rich-text :deep(.tiptap p:first-child),
.rich-text :deep(.tiptap h2:first-child),
.rich-text :deep(.tiptap h3:first-child) { margin-top: 0; }
.rich-text :deep(.tiptap p:last-child) { margin-bottom: 0; }
</style>

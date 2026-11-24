<template>
  <div class="page system-page">
    <div class="row-between page-head">
      <div>
        <h2 class="page-title">角色管理</h2>
        <p class="page-subtitle">OWNER 与 MEMBER 为内置角色，编码不可修改。</p>
      </div>
      <a-button type="primary" @click="openCreate">新增角色</a-button>
    </div>

    <section class="surface">
      <a-table :columns="columns" :data-source="rows" :loading="loading" row-key="id" size="middle">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'enable'">
            <a-tag :color="record.enable === 'Y' ? 'green' : 'default'">
              {{ record.enable === 'Y' ? '启用' : '停用' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
          </template>
        </template>
      </a-table>
    </section>

    <a-modal
      v-model:open="editorOpen"
      :title="editor.id ? '编辑角色' : '新增角色'"
      :confirm-loading="saving"
      @ok="save"
    >
      <a-form layout="vertical">
        <a-form-item label="角色编码">
          <a-input v-model:value="editor.code" :disabled="builtin" placeholder="如 VIEWER" />
        </a-form-item>
        <a-form-item label="角色名称">
          <a-input v-model:value="editor.name" />
        </a-form-item>
        <a-form-item label="描述">
          <a-input v-model:value="editor.description" />
        </a-form-item>
        <a-form-item label="状态">
          <a-radio-group v-model:value="editor.enable">
            <a-radio value="Y">启用</a-radio>
            <a-radio value="N">停用</a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { message } from 'antdv-next'
import { computed, onMounted, reactive, ref } from 'vue'

import { systemApi } from '@/api/api'

const rows = ref([])
const loading = ref(false)
const saving = ref(false)
const editorOpen = ref(false)
const editor = reactive({ id: null, code: '', name: '', enable: 'Y', description: '' })

const columns = [
  { title: '编码', dataIndex: 'code', key: 'code', width: 140 },
  { title: '名称', dataIndex: 'name', key: 'name', width: 160 },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '状态', key: 'enable', width: 100 },
  { title: '操作', key: 'action', width: 100 },
]

const builtin = computed(() => ['OWNER', 'MEMBER'].includes(editor.code) && Boolean(editor.id))

async function load() {
  loading.value = true
  try {
    const data = await systemApi.roleList()
    rows.value = data.list || []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(editor, { id: null, code: '', name: '', enable: 'Y', description: '' })
  editorOpen.value = true
}

function openEdit(record) {
  Object.assign(editor, { ...record })
  editorOpen.value = true
}

async function save() {
  if (!editor.code.trim() || !editor.name.trim()) {
    message.warning('请填写角色编码和名称')
    return
  }
  saving.value = true
  try {
    await systemApi.roleSave({
      id: editor.id || undefined,
      code: editor.code.trim(),
      name: editor.name.trim(),
      enable: editor.enable,
      description: editor.description,
    })
    message.success('已保存')
    editorOpen.value = false
    load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.system-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>

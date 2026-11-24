<template>
  <div class="page system-page">
    <div class="row-between page-head">
      <div>
        <h2 class="page-title">字典管理</h2>
        <p class="page-subtitle">维护情绪、媒体类型、注册模式等基础码值。</p>
      </div>
      <a-button type="primary" @click="openCreate">新增字典项</a-button>
    </div>

    <section class="surface">
      <div class="filter-row">
        <a-select
          v-model:value="codeid"
          :options="codeidOptions"
          placeholder="字典类型"
          allow-clear
          style="width: 200px"
          @change="load"
        />
        <a-button @click="load">刷新</a-button>
      </div>

      <a-table :columns="columns" :data-source="rows" :loading="loading" row-key="id" size="middle">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
          </template>
        </template>
      </a-table>
    </section>

    <a-modal
      v-model:open="editorOpen"
      :title="editor.id ? '编辑字典项' : '新增字典项'"
      :confirm-loading="saving"
      @ok="save"
    >
      <a-form layout="vertical">
        <a-form-item label="字典类型">
          <a-input v-model:value="editor.codeid" placeholder="如 MOOD" />
        </a-form-item>
        <a-form-item label="码值">
          <a-input v-model:value="editor.code" />
        </a-form-item>
        <a-form-item label="显示名">
          <a-input v-model:value="editor.name" />
        </a-form-item>
        <a-form-item label="备注">
          <a-input v-model:value="editor.remark" />
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
const allRows = ref([])
const loading = ref(false)
const saving = ref(false)
const codeid = ref(undefined)
const editorOpen = ref(false)
const editor = reactive({ id: null, codeid: '', code: '', name: '', remark: '' })

const columns = [
  { title: '字典类型', dataIndex: 'codeid', key: 'codeid', width: 140 },
  { title: '码值', dataIndex: 'code', key: 'code', width: 140 },
  { title: '显示名', dataIndex: 'name', key: 'name' },
  { title: '备注', dataIndex: 'remark', key: 'remark', ellipsis: true },
  { title: '操作', key: 'action', width: 90 },
]

const codeidOptions = computed(() => {
  const types = [...new Set(allRows.value.map((row) => row.codeid))]
  return types.map((value) => ({ label: value, value }))
})

async function load() {
  loading.value = true
  try {
    allRows.value = await systemApi.dictList()
    rows.value = codeid.value
      ? allRows.value.filter((row) => row.codeid === codeid.value)
      : allRows.value
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(editor, {
    id: null,
    codeid: codeid.value || '',
    code: '',
    name: '',
    remark: '',
  })
  editorOpen.value = true
}

function openEdit(record) {
  Object.assign(editor, { ...record })
  editorOpen.value = true
}

async function save() {
  if (!editor.codeid.trim() || !editor.code.trim() || !editor.name.trim()) {
    message.warning('请填写字典类型、码值和显示名')
    return
  }
  saving.value = true
  try {
    await systemApi.dictSave({
      id: editor.id || undefined,
      codeid: editor.codeid.trim(),
      code: editor.code.trim(),
      name: editor.name.trim(),
      remark: editor.remark,
    })
    message.success('已保存')
    editorOpen.value = false
    await load()
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

.filter-row {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}
</style>

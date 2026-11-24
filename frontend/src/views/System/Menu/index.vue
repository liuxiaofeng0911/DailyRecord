<template>
  <div class="page system-page">
    <div class="row-between page-head">
      <div>
        <h2 class="page-title">菜单管理</h2>
        <p class="page-subtitle">维护侧边栏菜单与分组，菜单路径需对应已有页面。</p>
      </div>
      <a-button type="primary" @click="openCreate()">新增菜单</a-button>
    </div>

    <section class="surface">
      <a-table
        :columns="columns"
        :data-source="rows"
        :loading="loading"
        row-key="id"
        size="middle"
        :default-expand-all-rows="true"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'icon'">
            <span class="icon-cell">
              <AppIcon :name="record.icon || 'lucide:circle'" :size="16" />
              {{ record.icon || '未设置' }}
            </span>
          </template>
          <template v-else-if="column.key === 'path'">
            <span v-if="record.path">{{ record.path }}</span>
            <span v-else class="muted">分组</span>
          </template>
          <template v-else-if="column.key === 'enable'">
            <a-tag :color="record.enable === 'Y' ? 'green' : 'default'">
              {{ record.enable === 'Y' ? '启用' : '停用' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="openCreate(record)">新增子菜单</a-button>
              <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
              <a-button type="link" size="small" danger @click="remove(record)">删除</a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </section>

    <a-modal
      v-model:open="editorOpen"
      :title="editor.id ? '编辑菜单' : '新增菜单'"
      :confirm-loading="saving"
      @ok="save"
    >
      <a-form layout="vertical">
        <a-form-item label="上级菜单">
          <a-select v-model:value="editor.pid" :options="parentOptions" />
        </a-form-item>
        <a-form-item label="菜单名称">
          <a-input v-model:value="editor.name" placeholder="如 用户管理" />
        </a-form-item>
        <a-form-item label="页面路径">
          <a-input v-model:value="editor.path" placeholder="如 /System/User；分组留空" />
        </a-form-item>
        <a-form-item label="图标">
          <a-select v-model:value="editor.icon" :options="iconOptions" allow-clear>
            <template #option="{ value }">
              <span class="icon-cell"><AppIcon :name="value" :size="16" />{{ labelOf(value) }}</span>
            </template>
          </a-select>
        </a-form-item>
        <a-form-item label="排序">
          <a-input-number v-model:value="editor.sort" :min="0" :max="999" style="width: 120px" />
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
import { Modal, message } from 'antdv-next'
import { computed, onMounted, reactive, ref } from 'vue'

import { systemApi } from '@/api/api'
import AppIcon from '@/components/AppIcon.vue'

const rows = ref([])
const loading = ref(false)
const saving = ref(false)
const editorOpen = ref(false)
const editor = reactive({
  id: null,
  pid: '0',
  name: '',
  path: '',
  icon: 'lucide:circle',
  sort: 0,
  enable: 'Y',
})

const ICONS = [
  ['lucide:calendar-heart', '今天'],
  ['lucide:history', '时间线'],
  ['lucide:chart-column', '统计'],
  ['lucide:settings', '系统'],
  ['lucide:settings-2', '设置'],
  ['lucide:user-round', '账户'],
  ['lucide:users', '用户'],
  ['lucide:shield-check', '角色'],
  ['lucide:building-2', '组织'],
  ['lucide:list-tree', '菜单'],
  ['lucide:book-open', '字典'],
  ['lucide:image', '相册'],
]
const iconOptions = ICONS.map(([value, label]) => ({ value, label }))

const columns = [
  { title: '菜单名称', dataIndex: 'name', key: 'name' },
  { title: '路径', key: 'path', width: 220 },
  { title: '图标', key: 'icon', width: 180 },
  { title: '排序', dataIndex: 'sort', key: 'sort', width: 80 },
  { title: '状态', key: 'enable', width: 90 },
  { title: '操作', key: 'action', width: 260 },
]

function labelOf(value) {
  return ICONS.find(([icon]) => icon === value)?.[1] || value
}

function flatten(nodes, depth = 0, result = []) {
  ;(nodes || []).forEach((node) => {
    result.push({ ...node, depth })
    flatten(node.children, depth + 1, result)
  })
  return result
}

const parentOptions = computed(() => [
  { value: '0', label: '顶级菜单' },
  ...flatten(rows.value)
    .filter((node) => node.id !== editor.id)
    .map((node) => ({
      value: node.id,
      label: `${'　'.repeat(node.depth)}${node.name}${node.path ? '' : '（分组）'}`,
    })),
])

async function load() {
  loading.value = true
  try {
    rows.value = (await systemApi.menuTree()) || []
  } finally {
    loading.value = false
  }
}

function openCreate(parent) {
  Object.assign(editor, {
    id: null,
    pid: parent?.id || '0',
    name: '',
    path: '',
    icon: 'lucide:circle',
    sort: 0,
    enable: 'Y',
  })
  editorOpen.value = true
}

function openEdit(record) {
  Object.assign(editor, {
    id: record.id,
    pid: record.pid || '0',
    name: record.name,
    path: record.path || '',
    icon: record.icon || 'lucide:circle',
    sort: record.sort || 0,
    enable: record.enable || 'Y',
  })
  editorOpen.value = true
}

async function save() {
  if (!editor.name.trim()) {
    message.warning('请填写菜单名称')
    return
  }
  saving.value = true
  try {
    await systemApi.menuSave({
      id: editor.id || undefined,
      name: editor.name.trim(),
      path: editor.path.trim(),
      icon: editor.icon,
      pid: editor.pid,
      sort: editor.sort,
      enable: editor.enable,
    })
    message.success('菜单已保存')
    editorOpen.value = false
    load()
  } finally {
    saving.value = false
  }
}

function remove(record) {
  Modal.confirm({
    title: `删除菜单「${record.name}」？`,
    content: '删除后相关角色将不再看到该菜单，此操作不可恢复。',
    okText: '删除',
    okType: 'danger',
    onOk: async () => {
      await systemApi.menuDelete(record.id)
      message.success('菜单已删除')
      load()
    },
  })
}

onMounted(load)
</script>

<style scoped lang="less">
.system-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.icon-cell {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--app-text-2);
}
</style>

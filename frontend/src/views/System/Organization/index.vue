<template>
  <div class="page system-page">
    <div class="row-between page-head">
      <div>
        <h2 class="page-title">组织管理</h2>
        <p class="page-subtitle">维护组织层级与成员，按组织控制共享开关。</p>
      </div>
      <a-space>
        <a-button @click="openShare()">成员记录共享</a-button>
        <a-button type="primary" @click="openCreate()">新增组织</a-button>
      </a-space>
    </div>

    <section class="surface">
      <a-table
        :columns="columns"
        :data-source="treeRows"
        :loading="loading"
        row-key="id"
        size="middle"
        :default-expand-all-rows="true"
        :scroll="{ x: 1290 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="record.status === 'Y' ? 'green' : 'default'">
              {{ record.status === 'Y' ? '启用' : '停用' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'share'">
            <a-space>
              <a-switch
                :checked="record.shareEnabled"
                :loading="shareSaving === record.id"
                @change="(checked) => toggleShare(record, checked)"
              />
              <span class="muted">{{ record.shareEnabled ? '共享中' : '已暂停' }}</span>
            </a-space>
          </template>
          <template v-else-if="column.key === 'remark'">
            <span class="muted">{{ record.remark || '-' }}</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="openMembers(record)">成员</a-button>
              <a-button type="link" size="small" @click="openShare(record)">共享记录</a-button>
              <a-button type="link" size="small" @click="openCreate(record)">新增子组织</a-button>
              <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
              <a-button
                type="link"
                size="small"
                danger
                :disabled="record.id === '1'"
                @click="remove(record)"
              >
                删除
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </section>

    <a-modal
      v-model:open="memberOpen"
      :title="`组织成员${memberOrg ? '：' + memberOrg.orgName : ''}`"
      :confirm-loading="memberSaving"
      @ok="saveMembers"
    >
      <p class="muted member-hint">
        同一用户可同时加入多个组织；所有者不属于任何组织，可查看全部成员记录。
      </p>
      <a-select
        v-model:value="memberIds"
        mode="multiple"
        :options="memberOptions"
        :loading="memberLoading"
        show-search
        option-filter-prop="label"
        placeholder="选择组织成员"
        style="width: 100%"
      />
    </a-modal>

    <a-modal
      v-model:open="editorOpen"
      :title="editor.id ? '编辑组织' : '新增组织'"
      :confirm-loading="saving"
      @ok="save"
    >
      <a-form layout="vertical">
        <a-form-item label="上级组织">
          <a-select v-model:value="editor.pid" :options="parentOptions" />
        </a-form-item>
        <a-form-item label="组织编码">
          <a-input v-model:value="editor.orgCode" placeholder="如 LAB" />
        </a-form-item>
        <a-form-item label="组织名称">
          <a-input v-model:value="editor.orgName" placeholder="如 实验室" />
        </a-form-item>
        <a-form-item label="状态">
          <a-radio-group v-model:value="editor.status">
            <a-radio value="Y">启用</a-radio>
            <a-radio value="N">停用</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="备注">
          <a-input v-model:value="editor.remark" />
        </a-form-item>
      </a-form>
    </a-modal>

    <OrgShareDrawer v-model:open="shareOpen" :orgs="rows" :org-id="shareOrgId" />
  </div>
</template>

<script setup>
import { Modal, message } from 'antdv-next'
import { computed, onMounted, reactive, ref } from 'vue'

import { systemApi } from '@/api/api'
import OrgShareDrawer from '@/components/OrgShareDrawer.vue'

const rows = ref([])
const loading = ref(false)
const saving = ref(false)
const editorOpen = ref(false)
const shareOpen = ref(false)
const shareOrgId = ref('')
const shareSaving = ref('')
const memberOpen = ref(false)
const memberOrg = ref(null)
const memberLoading = ref(false)
const memberSaving = ref(false)
const memberIds = ref([])
const memberOptions = ref([])
const editor = reactive({
  id: null,
  pid: '0',
  orgCode: '',
  orgName: '',
  status: 'Y',
  remark: '',
})

const columns = [
  { title: '组织名称', dataIndex: 'orgName', key: 'orgName', width: 240 },
  { title: '组织编码', dataIndex: 'orgCode', key: 'orgCode', width: 150 },
  { title: '状态', key: 'status', width: 90 },
  { title: '共享', key: 'share', width: 150 },
  { title: '备注', key: 'remark', width: 280, ellipsis: true },
  { title: '操作', key: 'action', width: 380 },
]

const treeRows = computed(() => {
  const map = new Map(rows.value.map((row) => [row.id, { ...row, children: [] }]))
  const roots = []
  map.forEach((node) => {
    const parent = node.pid && node.pid !== '0' ? map.get(node.pid) : null
    if (parent) parent.children.push(node)
    else roots.push(node)
  })
  return roots
})

const parentOptions = computed(() => [
  { value: '0', label: '顶级组织' },
  ...rows.value
    .filter((row) => row.id !== editor.id)
    .map((row) => ({ value: row.id, label: `${row.orgName}（${row.orgCode}）` })),
])

async function load() {
  loading.value = true
  try {
    rows.value = (await systemApi.orgTree()) || []
  } finally {
    loading.value = false
  }
}

function openCreate(parent) {
  Object.assign(editor, {
    id: null,
    pid: parent?.id || '0',
    orgCode: '',
    orgName: '',
    status: 'Y',
    remark: '',
  })
  editorOpen.value = true
}

function openEdit(record) {
  Object.assign(editor, {
    id: record.id,
    pid: record.pid || '0',
    orgCode: record.orgCode,
    orgName: record.orgName,
    status: record.status,
    remark: record.remark || '',
  })
  editorOpen.value = true
}

function openShare(record) {
  shareOrgId.value = record?.id || ''
  shareOpen.value = true
}

async function toggleShare(record, checked) {
  shareSaving.value = record.id
  try {
    const data = await systemApi.orgShareSwitch({ id: record.id, enabled: checked })
    record.shareEnabled = Boolean(data.shareEnabled)
    rows.value = rows.value.map((row) =>
      row.id === record.id ? { ...row, shareEnabled: record.shareEnabled } : row,
    )
    message.success(record.shareEnabled ? '已开启该组织共享' : '已暂停该组织共享')
  } catch {
    record.shareEnabled = !checked
  } finally {
    shareSaving.value = ''
  }
}

async function openMembers(record) {
  memberOrg.value = record
  memberIds.value = []
  memberOptions.value = []
  memberOpen.value = true
  memberLoading.value = true
  try {
    const data = await systemApi.orgMembers(record.id)
    memberIds.value = data.memberIds || []
    memberOptions.value = (data.candidates || []).map((row) => ({
      value: row.id,
      label: `${row.username}（${row.userid}）`,
    }))
  } finally {
    memberLoading.value = false
  }
}

async function saveMembers() {
  if (!memberOrg.value) return
  memberSaving.value = true
  try {
    await systemApi.orgMembersSave({
      id: memberOrg.value.id,
      userIds: memberIds.value,
    })
    message.success('组织成员已保存')
    memberOpen.value = false
  } finally {
    memberSaving.value = false
  }
}

async function save() {
  if (!editor.orgCode.trim() || !editor.orgName.trim()) {
    message.warning('请填写组织编码和名称')
    return
  }
  saving.value = true
  try {
    await systemApi.orgSave({
      id: editor.id || undefined,
      pid: editor.pid,
      orgCode: editor.orgCode.trim(),
      orgName: editor.orgName.trim(),
      status: editor.status,
      remark: editor.remark,
    })
    message.success('组织已保存')
    editorOpen.value = false
    load()
  } finally {
    saving.value = false
  }
}

function remove(record) {
  Modal.confirm({
    title: `删除组织「${record.orgName}」？`,
    content: '存在下级组织或用户时无法删除，请先处理。',
    okText: '删除',
    okType: 'danger',
    onOk: async () => {
      await systemApi.orgDelete(record.id)
      message.success('组织已删除')
      load()
    },
  })
}

onMounted(load)
</script>

<style scoped>
.system-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-7);
}

.member-hint {
  margin: 0 0 12px;
  font-size: 12px;
  line-height: 1.7;
}
</style>

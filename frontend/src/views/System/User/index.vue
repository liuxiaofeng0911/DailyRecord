<template>
  <div class="page system-page">
    <div class="row-between page-head">
      <div>
        <h2 class="page-title">用户管理</h2>
        <p class="page-subtitle">管理账号、角色与启用状态，仅所有者可见。</p>
      </div>
      <a-button type="primary" @click="openCreate">新增用户</a-button>
    </div>

    <section class="surface">
      <div class="filter-row">
        <a-input v-model:value="query.keyword" placeholder="账号 / 显示名 / 邮箱" allow-clear style="width: 240px" />
        <a-select v-model:value="query.active" placeholder="状态" allow-clear style="width: 120px">
          <a-select-option value="Y">启用</a-select-option>
          <a-select-option value="N">禁用</a-select-option>
        </a-select>
        <a-button type="primary" @click="load(1)">查询</a-button>
        <a-button @click="resetQuery">重置</a-button>
      </div>

      <a-table
        :columns="columns"
        :data-source="rows"
        :loading="loading"
        :pagination="false"
        row-key="id"
        size="middle"
        :scroll="{ x: 960 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'active'">
            <a-tag :color="record.userActive === 'Y' ? 'green' : 'default'">
              {{ record.userActive === 'Y' ? '启用' : '禁用' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'locked'">
            <a-tag v-if="record.lockedUntil" color="orange">锁定中</a-tag>
            <span v-else class="muted">-</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
              <a-button type="link" size="small" @click="openReset(record)">重置密码</a-button>
              <a-button
                type="link"
                size="small"
                danger
                :disabled="record.userActive !== 'Y'"
                @click="disableUser(record)"
              >
                禁用
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>

      <div class="pagination-row">
        <a-pagination
          :current="page"
          :page-size="pageSize"
          :total="total"
          show-less-items
          @change="load"
        />
      </div>
    </section>

    <a-modal
      v-model:open="editorOpen"
      :title="editor.id ? '编辑用户' : '新增用户'"
      :confirm-loading="saving"
      @ok="saveUser"
    >
      <a-form layout="vertical">
        <a-form-item label="登录账号">
          <a-input
            v-model:value="editor.userid"
            :disabled="Boolean(editor.id)"
            placeholder="2-32 位字母、数字、下划线或中文"
          />
        </a-form-item>
        <a-form-item label="显示名">
          <a-input v-model:value="editor.username" />
        </a-form-item>
        <a-form-item label="邮箱">
          <a-input v-model:value="editor.email" />
        </a-form-item>
        <a-form-item :label="editor.id ? '新密码（留空则不修改）' : '初始密码'">
          <a-input-password v-model:value="editor.password" placeholder="至少 10 位" />
        </a-form-item>
        <a-form-item label="角色">
          <a-select v-model:value="editor.roleCode" :options="roleOptions" />
        </a-form-item>
        <a-form-item label="状态">
          <a-radio-group v-model:value="editor.userActive">
            <a-radio value="Y">启用</a-radio>
            <a-radio value="N">禁用</a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="resetOpen"
      title="重置密码"
      :confirm-loading="saving"
      @ok="resetPassword"
    >
      <p class="muted">重置后该用户所有登录会话会立即失效。</p>
      <a-input-password v-model:value="resetValue" placeholder="新密码，至少 10 位" />
    </a-modal>
  </div>
</template>

<script setup>
import { Modal, message } from 'antdv-next'
import { computed, onMounted, reactive, ref } from 'vue'

import { systemApi } from '@/api/api'
import { encrypt } from '@/api/crypto'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const roles = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const query = reactive({ keyword: '', active: undefined })

const editorOpen = ref(false)
const editor = reactive({
  id: null,
  userid: '',
  username: '',
  email: '',
  password: '',
  roleCode: 'MEMBER',
  userActive: 'Y',
})
const resetOpen = ref(false)
const resetTarget = ref(null)
const resetValue = ref('')

const columns = [
  { title: '账号', dataIndex: 'userid', key: 'userid', width: 140 },
  { title: '显示名', dataIndex: 'username', key: 'username', width: 120 },
  { title: '邮箱', dataIndex: 'email', key: 'email', ellipsis: true },
  { title: '角色', dataIndex: 'roleCode', key: 'roleCode', width: 100 },
  { title: '状态', key: 'active', width: 90 },
  { title: '锁定', key: 'locked', width: 90 },
  { title: '最近登录', dataIndex: 'loginTime', key: 'loginTime', width: 170 },
  { title: '操作', key: 'action', width: 220 },
]

const roleOptions = computed(() =>
  roles.value.filter((role) => role.enable === 'Y').map((role) => ({
    label: role.name,
    value: role.code,
  })),
)

async function load(nextPage = page.value) {
  page.value = nextPage
  loading.value = true
  try {
    const wheres = []
    if (query.keyword.trim()) {
      wheres.push({ column: 'keyword', condition: 'eq', v1: query.keyword.trim() })
    }
    if (query.active) wheres.push({ column: 'user_active', condition: 'eq', v1: query.active })
    const data = await systemApi.userList({
      page: { pageNumber: page.value, pageSize: pageSize.value },
      wheres,
    })
    rows.value = data.list || []
    total.value = data.totalRow || 0
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  query.keyword = ''
  query.active = undefined
  load(1)
}

function openCreate() {
  Object.assign(editor, {
    id: null,
    userid: '',
    username: '',
    email: '',
    password: '',
    roleCode: 'MEMBER',
    userActive: 'Y',
  })
  editorOpen.value = true
}

function openEdit(record) {
  Object.assign(editor, {
    id: record.id,
    userid: record.userid,
    username: record.username,
    email: record.email,
    password: '',
    roleCode: record.roleCode,
    userActive: record.userActive,
  })
  editorOpen.value = true
}

async function saveUser() {
  if (!editor.userid.trim() || !editor.username.trim() || !editor.email.trim()) {
    message.warning('请填写账号、显示名和邮箱')
    return
  }
  if (!editor.id && editor.password.length < 10) {
    message.warning('初始密码至少 10 位')
    return
  }
  saving.value = true
  try {
    await systemApi.userSave({
      id: editor.id || undefined,
      userid: editor.userid.trim(),
      username: editor.username.trim(),
      email: editor.email.trim(),
      password: editor.password ? await encrypt(editor.password) : undefined,
      roleCode: editor.roleCode,
      userActive: editor.userActive,
    })
    message.success('已保存')
    editorOpen.value = false
    load()
  } finally {
    saving.value = false
  }
}

function openReset(record) {
  resetTarget.value = record
  resetValue.value = ''
  resetOpen.value = true
}

async function resetPassword() {
  if (resetValue.value.length < 10) {
    message.warning('新密码至少 10 位')
    return
  }
  saving.value = true
  try {
    await systemApi.userResetPassword({
      id: resetTarget.value.id,
      password: await encrypt(resetValue.value),
    })
    message.success('密码已重置')
    resetOpen.value = false
  } finally {
    saving.value = false
  }
}

function disableUser(record) {
  Modal.confirm({
    title: `禁用 ${record.userid}？`,
    content: '该用户的所有会话会立即失效。',
    okText: '禁用',
    okType: 'danger',
    onOk: async () => {
      await systemApi.userDelete(record.id)
      message.success('已禁用')
      load()
    },
  })
}

onMounted(async () => {
  const data = await systemApi.roleList()
  roles.value = data.list || []
  load(1)
})
</script>

<style scoped lang="less">
.system-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-7);
}

.filter-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>

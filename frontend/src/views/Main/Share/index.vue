<template>
  <div class="page share-page">
    <div class="row-between page-head">
      <div>
        <h2 class="page-title">共享</h2>
        <p class="page-subtitle">组织内成员双向确认后才互相可见；组织可随时暂停共享。</p>
      </div>
      <a-space class="org-tools" wrap>
        <a-select
          v-model:value="orgId"
          :options="orgOptions"
          placeholder="选择组织"
          class="org-select"
          @change="onOrgChange"
        />
        <a-tag v-if="currentOrg" :color="currentOrg.shareEnabled ? 'green' : 'default'">
          {{ currentOrg.shareEnabled ? '共享开启' : '共享已暂停' }}
        </a-tag>
      </a-space>
    </div>

    <a-empty v-if="!loadingOrgs && !orgs.length" description="你还未加入任何组织，请联系所有者分配" />

    <template v-else-if="config">
      <a-alert
        v-if="!config.shareEnabled"
        type="warning"
        show-icon
        message="该组织共享已被暂停"
        description="组织内所有人都暂时无法查看彼此记录；你已配置的可见人员会保留，开关恢复后继续生效。"
      />
      <a-alert
        v-else-if="config.isOwner"
        type="info"
        show-icon
        message="所有者视角"
        description="所有者不属于任何组织，可以直接查看所选组织内全部成员的记录。"
      />

      <section v-if="!config.isOwner" class="surface share-config">
        <div class="config-block">
          <h3 class="config-title">允许查看我的人</h3>
          <p class="muted config-desc">被选中的人可以查看我的每日记录，未选中的人看不到。</p>
          <a-select
            v-model:value="allowIds"
            mode="multiple"
            :options="memberOptions"
            :disabled="!config.shareEnabled"
            show-search
            option-filter-prop="label"
            placeholder="选择允许查看我记录的人"
            style="width: 100%"
          />
        </div>
        <div class="config-block">
          <h3 class="config-title">我想查看的人</h3>
          <p class="muted config-desc">只有“对方允许我看 + 我也选中对方”时，才会出现在下方共享记录中。</p>
          <a-select
            v-model:value="watchIds"
            mode="multiple"
            :options="memberOptions"
            :disabled="!config.shareEnabled"
            show-search
            option-filter-prop="label"
            placeholder="选择我想查看记录的人"
            style="width: 100%"
          />
        </div>
        <div class="row-between config-actions">
          <span class="muted">配置保存后立即生效。</span>
          <a-button
            type="primary"
            :loading="savingConfig"
            :disabled="!config.shareEnabled"
            @click="saveConfig"
          >
            保存配置
          </a-button>
        </div>
      </section>

      <section class="surface">
        <div class="row-between section-head">
          <h3 class="section-title">{{ config.isOwner ? '组织成员记录' : '共享给我的记录' }}</h3>
          <div class="filter-row">
            <a-range-picker
              v-model:value="filters.range"
              class="share-range"
              format="YYYY-MM-DD"
              :placeholder="['开始日期', '结束日期']"
              @change="reloadEntries"
            />
            <a-input-search
              v-model:value="filters.keyword"
              class="share-search"
              placeholder="搜索记录内容"
              allow-clear
              @search="reloadEntries"
            />
          </div>
        </div>

        <a-spin :spinning="loadingEntries">
          <div v-if="entries.length" class="share-list">
            <article v-for="item in entries" :key="item.id" class="share-item">
              <header class="share-head">
                <a-avatar :size="26">{{ (item.username || '?').slice(0, 1) }}</a-avatar>
                <strong>{{ item.username || item.userid }}</strong>
                <span class="muted">{{ item.entryDate }}</span>
                <a-tag v-if="item.mood" color="blue">{{ item.mood }}</a-tag>
              </header>
              <p v-if="item.note" class="share-note">{{ item.note }}</p>
              <p v-else class="muted share-note">这天没有文字内容</p>
              <div v-if="item.tags?.length" class="share-tags">
                <a-tag v-for="tag in item.tags" :key="tag.id">#{{ tag.name }}</a-tag>
              </div>
              <div v-if="item.photos?.length" class="share-photos">
                <div v-for="photo in item.photos" :key="photo.id" class="share-photo">
                  <img :src="thumbUrl(photo)" :alt="photo.caption || '照片'" loading="lazy" />
                  <span v-if="photo.mediaType === 'VIDEO'" class="video-badge">视频</span>
                </div>
              </div>
            </article>
          </div>
          <a-empty v-else description="暂时没有可查看的共享记录" />
        </a-spin>

        <div v-if="total > pageSize" class="share-pager">
          <a-pagination
            :current="pageNumber"
            :page-size="pageSize"
            :total="total"
            size="small"
            show-less-items
            @change="onPageChange"
          />
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import dayjs from 'dayjs'
import { message } from 'antdv-next'
import { computed, onMounted, reactive, ref } from 'vue'
import { useStore } from 'vuex'

import { orgShareApi, photoApi } from '@/api/api'

const store = useStore()
const isOwner = computed(() => store.getters['auth/isOwner'])
const myId = computed(() => store.state.auth.userInfo?.id)

const loadingOrgs = ref(false)
const orgs = ref([])
const orgId = ref(undefined)
const config = ref(null)
const allowIds = ref([])
const watchIds = ref([])
const savingConfig = ref(false)

const entries = ref([])
const loadingEntries = ref(false)
const total = ref(0)
const pageNumber = ref(1)
const pageSize = ref(20)
const filters = reactive({
  range: [dayjs().subtract(29, 'day'), dayjs()],
  keyword: '',
})

const currentOrg = computed(() => orgs.value.find((row) => row.id === orgId.value))
const orgOptions = computed(() =>
  orgs.value.map((row) => ({
    value: row.id,
    label: `${row.orgName}（${row.orgCode}）${row.shareEnabled ? '' : ' · 已暂停'}`,
  })),
)
const memberOptions = computed(() =>
  (config.value?.members || [])
    .filter((row) => row.id !== myId.value)
    .map((row) => ({ value: row.id, label: `${row.username}（${row.userid}）` })),
)

function thumbUrl(photo) {
  return `${photoApi.thumbnail(photo.id)}?v=${photo.version || 0}`
}

function buildEntriesPayload() {
  const payload = {
    orgId: orgId.value || undefined,
    page: { pageNumber: pageNumber.value, pageSize: pageSize.value },
  }
  if (filters.range?.length === 2) {
    payload.start = filters.range[0].format('YYYY-MM-DD')
    payload.end = filters.range[1].format('YYYY-MM-DD')
  }
  if (filters.keyword.trim()) payload.keyword = filters.keyword.trim()
  return payload
}

async function loadOrgs() {
  loadingOrgs.value = true
  try {
    orgs.value = (await orgShareApi.myOrgs()) || []
    if (!orgId.value && orgs.value.length) orgId.value = orgs.value[0].id
  } finally {
    loadingOrgs.value = false
  }
}

async function loadConfig() {
  if (!orgId.value) return
  config.value = (await orgShareApi.myConfig(orgId.value)) || null
  allowIds.value = config.value?.allowIds || []
  watchIds.value = config.value?.watchIds || []
}

async function loadEntries() {
  if (!orgId.value) return
  loadingEntries.value = true
  try {
    const data = await orgShareApi.myEntries(buildEntriesPayload())
    entries.value = data.list || []
    total.value = data.totalRow || 0
  } finally {
    loadingEntries.value = false
  }
}

function reloadEntries() {
  pageNumber.value = 1
  loadEntries()
}

function onPageChange(next) {
  pageNumber.value = next
  loadEntries()
}

async function onOrgChange() {
  await loadConfig()
  reloadEntries()
}

async function saveConfig() {
  if (!config.value) return
  savingConfig.value = true
  try {
    config.value = await orgShareApi.myConfigSave({
      orgId: orgId.value,
      allowIds: allowIds.value,
      watchIds: watchIds.value,
    })
    allowIds.value = config.value?.allowIds || []
    watchIds.value = config.value?.watchIds || []
    message.success('共享配置已保存')
    loadEntries()
  } finally {
    savingConfig.value = false
  }
}

onMounted(async () => {
  await loadOrgs()
  if (orgId.value) {
    await loadConfig()
    reloadEntries()
  }
})
</script>

<style scoped lang="less">
.share-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.page-head {
  flex-wrap: wrap;
  gap: var(--space-3);
}

.org-select {
  width: 240px;
}

.share-range {
  width: 260px;
}

.share-search {
  width: 200px;
}

.share-config {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.config-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.config-title {
  margin: 0;
  font-size: 14px;
  color: var(--app-text-1);
}

.config-desc {
  margin: 0;
  font-size: 12px;
  line-height: 1.7;
}

.config-actions {
  align-items: center;
  padding-top: var(--space-3);
  border-top: 1px solid var(--app-border);
}

.section-head {
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.section-title {
  margin: 0;
  font-size: 14px;
  color: var(--app-text-1);
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.share-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.share-item {
  padding: var(--space-3);
  border: 1px solid var(--app-border);
  border-radius: var(--radius-control);
  background: var(--app-bg-elevated);
}

.share-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 13px;
  margin-bottom: var(--space-2);
}

.share-note {
  margin: 0 0 var(--space-2);
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--app-text-1);
}

.share-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: var(--space-2);
}

.share-photos {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: 8px;
}

.share-photo {
  position: relative;
  aspect-ratio: 1;
  border-radius: 10px;
  overflow: hidden;
  background: var(--app-bg-body);
  border: 1px solid var(--app-border);

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
}

.video-badge {
  position: absolute;
  left: 6px;
  bottom: 6px;
  padding: 1px 6px;
  border-radius: var(--radius-pill);
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 10px;
}

.share-pager {
  display: flex;
  justify-content: center;
  margin-top: var(--space-4);
}

@media (max-width: 768px) {
  .page-head {
    flex-direction: column;
    align-items: stretch;
  }

  .org-tools {
    width: 100%;
  }

  :deep(.org-tools .ant-space-item) {
    width: 100%;
  }

  .org-select,
  .share-range,
  .share-search {
    width: 100%;
  }

  .filter-row {
    width: 100%;
  }

  .share-photos {
    grid-template-columns: repeat(auto-fill, minmax(78px, 1fr));
  }
}
</style>

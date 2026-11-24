<template>
  <a-modal
    :open="open"
    title="修改密码"
    :confirm-loading="loading"
    ok-text="确认修改"
    cancel-text="取消"
    @ok="submit"
    @cancel="$emit('update:open', false)"
  >
    <a-form layout="vertical">
      <a-form-item label="原密码">
        <a-input-password v-model:value="form.oldPassword" autocomplete="current-password" />
      </a-form-item>
      <a-form-item label="新密码">
        <a-input-password v-model:value="form.newPassword" placeholder="至少 10 位" autocomplete="new-password" />
      </a-form-item>
      <a-form-item label="确认新密码">
        <a-input-password v-model:value="form.confirmPassword" autocomplete="new-password" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup>
import { message } from 'antdv-next'
import { reactive, ref } from 'vue'
import { useStore } from 'vuex'

import { authApi } from '@/api/api'
import { encrypt } from '@/api/crypto'

defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['update:open', 'success'])
const store = useStore()
const loading = ref(false)
const form = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' })

async function submit() {
  if (!form.oldPassword || !form.newPassword) {
    message.warning('请填写原密码和新密码')
    return
  }
  if (form.newPassword.length < 10) {
    message.warning('新密码至少 10 位')
    return
  }
  if (form.newPassword !== form.confirmPassword) {
    message.warning('两次输入的新密码不一致')
    return
  }
  loading.value = true
  try {
    await authApi.changePassword({
      oldPassword: await encrypt(form.oldPassword),
      newPassword: await encrypt(form.newPassword),
      confirmPassword: await encrypt(form.confirmPassword),
    })
    message.success('密码已修改，请重新登录')
    emit('update:open', false)
    emit('success')
    await store.dispatch('auth/logout')
    window.location.hash = '#/Login'
  } finally {
    loading.value = false
  }
}
</script>

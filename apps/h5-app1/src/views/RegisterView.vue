<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { BaseButton } from '@my-robot/ui'

const route = useRoute()
const router = useRouter()

const department = ref(String(route.query.department ?? ''))
const departmentId = ref(String(route.query.departmentId ?? ''))
const date = ref(today())
const period = ref<'上午' | '下午'>('上午')
const confirmed = ref(false)

function today(): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

const canSubmit = computed(() => Boolean(department.value) && Boolean(date.value))

function submit() {
  if (!canSubmit.value) return
  confirmed.value = true
}
</script>

<template>
  <div class="register">
    <header class="register-header">
      <button
        class="back-btn"
        aria-label="返回"
        @click="router.back()"
      >
        ‹
      </button>
      <span class="register-title">门诊挂号</span>
      <span class="header-space" />
    </header>

    <div class="form">
      <label class="field">
        <span class="label">科室</span>
        <input
          v-model="department"
          class="input"
          placeholder="请选择科室"
        >
      </label>

      <label class="field">
        <span class="label">就诊日期</span>
        <input
          v-model="date"
          class="input"
          type="date"
        >
      </label>

      <div class="field">
        <span class="label">就诊时段</span>
        <div class="seg">
          <button
            class="seg-btn"
            :class="{ active: period === '上午' }"
            @click="period = '上午'"
          >
            上午
          </button>
          <button
            class="seg-btn"
            :class="{ active: period === '下午' }"
            @click="period = '下午'"
          >
            下午
          </button>
        </div>
      </div>

      <BaseButton
        type="primary"
        :disabled="!canSubmit"
        @click="submit"
      >
        确认挂号
      </BaseButton>

      <p
        v-if="confirmed"
        class="success"
      >
        挂号成功：{{ department }}（{{ departmentId }}） · {{ date }} · {{ period }}
      </p>
      <p class="tip">
        当前为演示流程，真实挂号请通过医院公众号或现场窗口办理。
      </p>
    </div>
  </div>
</template>

<style scoped>
.register {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  max-width: 720px;
  margin: 0 auto;
  background: #f5f7fa;
}

.register-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #eee;
  position: sticky;
  top: 0;
}

.back-btn {
  border: none;
  background: none;
  font-size: 28px;
  line-height: 1;
  cursor: pointer;
  color: #333;
  padding: 0 4px;
}

.register-title {
  font-size: 16px;
  font-weight: 600;
}

.header-space {
  width: 28px;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 16px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.label {
  font-size: 13px;
  color: #606266;
}

.input {
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  outline: none;
  background: #fff;
}

.input:focus {
  border-color: #409eff;
}

.seg {
  display: flex;
  gap: 8px;
}

.seg-btn {
  flex: 1;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 10px;
  font-size: 14px;
  background: #fff;
  cursor: pointer;
}

.seg-btn.active {
  border-color: #409eff;
  color: #409eff;
}

.success {
  color: #67c23a;
  font-size: 14px;
  text-align: center;
}

.tip {
  color: #909399;
  font-size: 12px;
  text-align: center;
}
</style>

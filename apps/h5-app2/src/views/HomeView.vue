<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { CompanionConversation } from '@my-robot/shared-types'
import { useCompanionStore } from '@/stores/companion'

const router = useRouter()
const store = useCompanionStore()

const recent = ref<CompanionConversation[]>([])

const features = [
  { icon: '💬', title: '随时倾诉', desc: '累了、烦了，随时有人陪你说说话' },
  { icon: '😴', title: '睡眠改善', desc: '入睡困难、睡不香，一起找原因' },
  { icon: '🥗', title: '健康饮食', desc: '一日三餐怎么吃更均衡更有活力' },
  { icon: '🧘', title: '情绪放松', desc: '压力与坏心情，聊聊更轻松' }
]

onMounted(async () => {
  recent.value = (await store.loadConversations()).slice(0, 3)
})
</script>

<template>
  <div class="home">
    <header class="hero">
      <p class="hero-label">
        健康陪伴助手
      </p>
      <h1 class="hero-title">
        小安，一直在你身边
      </h1>
      <p class="hero-desc">
        聊聊心情、问问健康、陪你放松 —— AI 陪伴，温暖每一刻
      </p>
      <button
        class="start-btn"
        @click="router.push('/companion')"
      >
        开始和小安聊天
      </button>
      <button
        class="smart-btn"
        @click="router.push('/companion/smart')"
      >
        健康陪伴智慧版 · 超拟人语音
      </button>
      <button
        class="smart-btn"
        @click="router.push('/companion/fast')"
      >
        健康陪伴快速版 · WebSocket 直连
      </button>
      <button
        class="smart-btn"
        @click="router.push('/science')"
      >
        科普百科助手 · 把知识讲明白
      </button>
      <p class="hero-tip">
        健康科普与陪伴，不替代专业医疗诊断
      </p>
    </header>

    <main class="body">
      <section
        v-if="recent.length"
        class="section"
      >
        <h2 class="section-title">
          最近对话
        </h2>
        <div
          v-for="c in recent"
          :key="c.id"
          class="recent-item"
          @click="router.push({ path: '/companion', query: { id: c.id } })"
        >
          <span class="recent-preview">{{ c.preview }}</span>
          <span class="recent-arrow">›</span>
        </div>
      </section>

      <section class="section">
        <h2 class="section-title">
          我能陪你做什么
        </h2>
        <div class="feature-grid">
          <div
            v-for="f in features"
            :key="f.title"
            class="feature-card"
          >
            <span class="feature-icon">{{ f.icon }}</span>
            <span class="feature-title">{{ f.title }}</span>
            <span class="feature-desc">{{ f.desc }}</span>
          </div>
        </div>
      </section>
    </main>

    <footer class="footer">
      <span>如遇紧急情况，请立即就医或拨打 120</span>
      <span
        class="footer-link"
        @click="router.push('/settings')"
      >设置</span>
    </footer>
  </div>
</template>

<style scoped>
.home {
  min-height: 100vh;
  max-width: 720px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.hero {
  background: linear-gradient(160deg, #eaf6ef 0%, #d3edda 60%, #b9e2c8 100%);
  padding: 56px 24px 40px;
  text-align: center;
}

.hero-label {
  display: inline-block;
  font-size: 12px;
  color: #3f9e4d;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 12px;
  padding: 4px 12px;
  margin: 0 0 16px;
}

.hero-title {
  font-size: 28px;
  margin: 0 0 12px;
  color: #1f3d2a;
  font-weight: 700;
}

.hero-desc {
  font-size: 15px;
  color: #4a7058;
  margin: 0 0 28px;
  line-height: 1.7;
}

.start-btn {
  border: none;
  background: linear-gradient(135deg, #67c23a, #3f9e4d);
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  border-radius: 26px;
  padding: 14px 40px;
  cursor: pointer;
  box-shadow: 0 8px 20px rgba(63, 158, 77, 0.35);
}

.start-btn:active {
  transform: scale(0.98);
}

.smart-btn {
  margin-top: 12px;
  border: 1px solid #3f9e4d;
  background: rgba(255, 255, 255, 0.85);
  color: #2e7d3d;
  font-size: 14px;
  font-weight: 600;
  border-radius: 24px;
  padding: 10px 26px;
  cursor: pointer;
}

.smart-btn:active {
  transform: scale(0.98);
}

.hero-tip {
  margin: 16px 0 0;
  font-size: 12px;
  color: #6b9c7c;
}

.body {
  flex: 1;
  padding: 20px 16px;
}

.section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 16px;
  color: #333;
  margin: 0 0 12px;
}

.recent-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 8px;
  cursor: pointer;
}

.recent-item:active {
  background: #f0f9f2;
}

.recent-preview {
  font-size: 14px;
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-arrow {
  color: #c0c4cc;
  font-size: 18px;
}

.feature-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.feature-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 14px;
  cursor: pointer;
}

.feature-card:active {
  background: #f0f9f2;
}

.feature-icon {
  font-size: 22px;
}

.feature-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.feature-desc {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}

.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px calc(14px + env(safe-area-inset-bottom));
  font-size: 12px;
  color: #909399;
  background: #fff;
  border-top: 1px solid #eee;
}

.footer-link {
  color: #67c23a;
  cursor: pointer;
}
</style>

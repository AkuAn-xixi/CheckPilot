<template>
  <transition name="exec-card-fade">
    <div v-if="visible" class="exec-card-wrap" :class="{ 'exec-card-wrap--collapsed': collapsed }">
      <!-- 折叠条：只显示模块名 + 状态 + 查看任务 + 展开箭头 -->
      <div v-if="collapsed" class="exec-card exec-card--collapsed">
        <span class="exec-card-badge" :class="`exec-card-badge--${executionState.activeType}`">{{ moduleLabel }}</span>
        <span class="exec-card-status" :class="`exec-card-status--${executionState.status}`">{{ statusLabel }}</span>
        <button type="button" class="exec-card-link" @click="goToModule">{{ $t('executionCard.enterModule') }}</button>
        <button
          type="button"
          class="exec-card-arrow"
          :title="$t('executionCard.expand')"
          @click="collapsed = false"
        >›</button>
      </div>

      <!-- 展开卡 -->
      <div v-else class="exec-card">
        <div class="exec-card-header">
          <div class="exec-card-badge" :class="`exec-card-badge--${executionState.activeType}`">{{ moduleLabel }}</div>
          <span class="exec-card-status" :class="`exec-card-status--${executionState.status}`">{{ statusLabel }}</span>
          <button
            v-if="executionState.status === 'running'"
            type="button"
            class="exec-card-link"
            @click="goToModule"
          >{{ $t('executionCard.enterModule') }}</button>
          <button
            type="button"
            class="exec-card-arrow"
            :title="$t('executionCard.collapse')"
            @click="collapsed = true"
          >‹</button>
        </div>

        <p v-if="executionState.label" class="exec-card-label">{{ executionState.label }}</p>

        <div class="exec-card-stats">
          <div class="exec-card-stat">
            <span class="exec-card-stat-num">{{ executionSummary.executed }}</span>
            <span class="exec-card-stat-key">{{ $t('executionCard.executed') }}</span>
          </div>
          <div class="exec-card-stat exec-card-stat--pass">
            <span class="exec-card-stat-num">{{ executionSummary.passed }}</span>
            <span class="exec-card-stat-key">{{ $t('executionCard.passed') }}</span>
          </div>
          <div class="exec-card-stat exec-card-stat--fail">
            <span class="exec-card-stat-num">{{ executionSummary.failed }}</span>
            <span class="exec-card-stat-key">{{ $t('executionCard.failed') }}</span>
          </div>
          <div class="exec-card-stat">
            <span class="exec-card-stat-num">
              {{ executionSummary.isInfinite ? $t('executionCard.unlimited') : executionSummary.pending }}
            </span>
            <span class="exec-card-stat-key">{{ $t('executionCard.pending') }}</span>
          </div>
        </div>

        <div v-if="!executionSummary.isInfinite" class="exec-card-progress">
          <div class="exec-card-progress-bar">
            <div class="exec-card-progress-fill" :style="{ width: `${progressPercent}%` }"></div>
          </div>
          <span class="exec-card-progress-text">{{ progressPercent }}%</span>
        </div>

        <div class="exec-card-actions">
          <button
            v-if="executionState.status === 'running'"
            type="button"
            class="exec-card-btn exec-card-btn--stop"
            @click="handleStop"
          >{{ $t('executionCard.stop') }}</button>
          <button
            v-else
            type="button"
            class="exec-card-btn"
            @click="resetExecution()"
          >{{ $t('executionCard.close') }}</button>
        </div>

        <div v-if="stopPrompt" class="exec-card-notice">{{ stopPrompt }}</div>
        <div v-else-if="executionState.blockNotice" class="exec-card-notice">{{ executionState.blockNotice }}</div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import {
  executionState,
  executionSummary,
  requestGlobalStop,
  resetExecution,
} from '../stores/executionStore'

const { t } = useI18n({ useScope: 'global' })
const router = useRouter()
const route = useRoute()

// 当前路由是否正好在正在执行的那个模块页面上（此时不显示小窗口）
const onModulePage = computed(() => {
  if (executionState.activeType === 'asr') {
    return route.path.startsWith('/excel/asr')
  }
  if (executionState.activeType === 'image') {
    return route.path.startsWith('/excel/cases')
  }
  return false
})

const visible = computed(() => (
  executionState.activeType !== null
  && executionState.status !== 'idle'
  && !onModulePage.value
))

// 显示 5 秒后自动折叠成小条；手动展开后不再自动折叠
const collapsed = ref(false)
let collapseTimer = null
const clearCollapseTimer = () => {
  if (collapseTimer) {
    clearTimeout(collapseTimer)
    collapseTimer = null
  }
}

watch(visible, (nowVisible) => {
  clearCollapseTimer()
  if (nowVisible) {
    collapsed.value = false
    collapseTimer = setTimeout(() => {
      collapsed.value = true
    }, 5000)
  }
}, { immediate: true })

// 停止执行：提示“任务已停止”后自动关闭小窗口
const stopPrompt = ref('')
let stopPromptTimer = null
const handleStop = () => {
  requestGlobalStop()
  stopPrompt.value = t('executionCard.stoppedPrompt')
  if (stopPromptTimer) {
    clearTimeout(stopPromptTimer)
  }
  stopPromptTimer = setTimeout(() => {
    stopPrompt.value = ''
    resetExecution()
  }, 1500)
}

onBeforeUnmount(() => {
  clearCollapseTimer()
  if (stopPromptTimer) {
    clearTimeout(stopPromptTimer)
  }
})

const moduleLabel = computed(() => {
  if (executionState.activeType === 'asr') {
    return t('executionCard.asrExecution')
  }
  return t('executionCard.imageExecution')
})

const statusLabel = computed(() => {
  const key = {
    running: 'executionCard.running',
    completed: 'executionCard.completed',
    stopped: 'executionCard.stopped',
  }[executionState.status]
  return key ? t(key) : ''
})

const progressPercent = computed(() => {
  const { total, executed } = executionSummary.value
  if (!total || total <= 0) {
    return 0
  }
  return Math.max(0, Math.min(100, Math.round((executed / total) * 100)))
})

const goToModule = () => {
  const target = executionState.activeType === 'asr' ? '/excel/asr' : '/excel/cases'
  if (router.currentRoute.value.path !== target) {
    router.push(target)
  }
}
</script>

<style scoped>
.exec-card-wrap {
  position: fixed;
  top: 18px;
  right: 24px;
  z-index: 60;
  width: 300px;
}

.exec-card-wrap--collapsed {
  width: auto;
  max-width: 340px;
}

.exec-card {
  position: relative;
  border-radius: 22px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.18);
  backdrop-filter: blur(20px);
  padding: 16px 18px 14px;
}

.exec-card--collapsed {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
}

.exec-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.exec-card-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 9999px;
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.exec-card-badge--image {
  background: rgba(14, 165, 233, 0.14);
  color: #0369a1;
}

.exec-card-badge--asr {
  background: rgba(147, 51, 234, 0.14);
  color: #7c3aed;
}

.exec-card-status {
  flex: 1;
  text-align: right;
  font-size: 0.74rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  white-space: nowrap;
}

.exec-card--collapsed .exec-card-status {
  flex: 0 1 auto;
}

.exec-card-status--running {
  color: #0ea5e9;
}

.exec-card-status--completed {
  color: #059669;
}

.exec-card-status--stopped {
  color: #d97706;
}

.exec-card-link {
  border: none;
  background: none;
  padding: 0;
  font-size: 0.72rem;
  font-weight: 600;
  color: #2563eb;
  cursor: pointer;
  text-decoration: underline;
  white-space: nowrap;
}

.exec-card-arrow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 1px solid rgba(203, 213, 225, 0.9);
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.9);
  color: #475569;
  font-size: 0.95rem;
  line-height: 1;
  cursor: pointer;
  transition: background-color 0.18s ease, transform 0.18s ease;
  flex-shrink: 0;
}

.exec-card-arrow:hover {
  transform: translateY(-1px);
  background: rgba(241, 245, 249, 0.95);
}

.exec-card-label {
  margin: 10px 0 0;
  font-size: 0.88rem;
  line-height: 1.45;
  color: #475569;
  overflow-wrap: anywhere;
}

.exec-card-stats {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
}

.exec-card-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 4px;
  border-radius: 12px;
  background: rgba(241, 245, 249, 0.8);
}

.exec-card-stat--pass .exec-card-stat-num {
  color: #059669;
}

.exec-card-stat--fail .exec-card-stat-num {
  color: #dc2626;
}

.exec-card-stat-num {
  font-size: 1.05rem;
  font-weight: 800;
  color: #0f172a;
  line-height: 1;
}

.exec-card-stat-key {
  font-size: 0.64rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: #64748b;
}

.exec-card-progress {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.exec-card-progress-bar {
  flex: 1;
  height: 6px;
  border-radius: 9999px;
  background: rgba(226, 232, 240, 0.9);
  overflow: hidden;
}

.exec-card-progress-fill {
  height: 100%;
  border-radius: 9999px;
  background: linear-gradient(90deg, rgba(14, 165, 233, 0.9), rgba(59, 130, 246, 0.9));
  transition: width 0.25s ease;
}

.exec-card-progress-text {
  font-size: 0.72rem;
  font-weight: 700;
  color: #475569;
  min-width: 32px;
  text-align: right;
}

.exec-card-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.exec-card-btn {
  border: 1px solid rgba(203, 213, 225, 0.9);
  background: rgba(255, 255, 255, 0.9);
  color: #475569;
  padding: 6px 14px;
  border-radius: 9999px;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.18s ease, transform 0.18s ease;
}

.exec-card-btn:hover {
  transform: translateY(-1px);
  background: rgba(241, 245, 249, 0.95);
}

.exec-card-btn--stop {
  border-color: rgba(220, 38, 38, 0.35);
  background: rgba(254, 226, 226, 0.9);
  color: #b91c1c;
}

.exec-card-btn--stop:hover {
  background: rgba(252, 165, 165, 0.55);
}

.exec-card-notice {
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(236, 253, 245, 0.9);
  border: 1px solid rgba(16, 185, 129, 0.25);
  color: #047857;
  font-size: 0.76rem;
  line-height: 1.4;
}

.exec-card-fade-enter-active,
.exec-card-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.exec-card-fade-enter-from,
.exec-card-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>

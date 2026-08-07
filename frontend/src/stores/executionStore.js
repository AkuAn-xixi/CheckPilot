// 全局执行状态 store（模块级单例，不随组件生命周期销毁）
//
// 图片执行（ExcelExecution.vue）与 ASR 执行（ExcelAsrAutomation.vue）在执行期间
// 把计数投影到这里，供全局右上角进度卡片与路由守卫读取。执行本身仍由视图组件驱动，
// 组件被 keep-alive 缓存后即使切换到其它页面，执行逻辑与连接也不会断开。
import { reactive, computed } from 'vue'

export const executionState = reactive({
  activeType: null, // 'image' | 'asr' | null
  status: 'idle', // 'idle' | 'running' | 'completed' | 'stopped'
  label: '',
  total: 0, // <=0 表示不限（无限循环）
  executed: 0,
  passed: 0,
  failed: 0,
  blockNotice: null, // 路由守卫拦截时的提示文案
})

export const isExecutionRunning = computed(() => executionState.status === 'running')

export const executionSummary = computed(() => ({
  total: executionState.total,
  executed: executionState.executed,
  passed: executionState.passed,
  failed: executionState.failed,
  pending: executionState.total > 0
    ? Math.max(0, executionState.total - executionState.executed)
    : 0,
  isInfinite: executionState.total <= 0,
}))

/**
 * 开始一次执行任务。若已有另一个模块在执行则拒绝并返回 false（互斥兜底）。
 * @param {{type: 'image'|'asr', label: string, total: number}} param0
 */
export function beginExecution({ type, label, total }) {
  if (executionState.status === 'running' && executionState.activeType !== type) {
    return false
  }
  executionState.activeType = type
  executionState.status = 'running'
  executionState.label = label || ''
  executionState.total = total || 0
  executionState.executed = 0
  executionState.passed = 0
  executionState.failed = 0
  executionState.blockNotice = null
  return true
}

/** 每完成一条（行/轮）调用一次。 */
export function recordRowResult({ passed }) {
  executionState.executed += 1
  if (passed) {
    executionState.passed += 1
  } else {
    executionState.failed += 1
  }
}

/** 任务结束（正常完成或停止）时调用。 */
export function finishExecution({ completed }) {
  executionState.status = completed ? 'completed' : 'stopped'
}

/** 关闭卡片并清空执行状态。 */
export function resetExecution() {
  executionState.activeType = null
  executionState.status = 'idle'
  executionState.label = ''
  executionState.total = 0
  executionState.executed = 0
  executionState.passed = 0
  executionState.failed = 0
  executionState.blockNotice = null
}

// ── 全局“停止执行”回调注册（由正在执行的视图注册，卡片按钮调用） ──
// 按模块类型区分存储，避免图片/ASR 两个视图（keep-alive 缓存下可能并存）互相覆盖。
const stopHandlers = {}

export function registerStopHandler(type, fn) {
  stopHandlers[type] = fn
}

export function unregisterStopHandler(type) {
  delete stopHandlers[type]
}

export function requestGlobalStop() {
  const fn = stopHandlers[executionState.activeType]
  if (fn) {
    fn()
  }
}

// ── 路由守卫拦截提示（toast） ──
let blockNoticeTimer = null

export function showBlockNotice(message) {
  executionState.blockNotice = message || ''
  if (blockNoticeTimer) {
    clearTimeout(blockNoticeTimer)
  }
  blockNoticeTimer = setTimeout(() => {
    executionState.blockNotice = null
    blockNoticeTimer = null
  }, 3000)
}

import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import DeviceManagement from '../views/DeviceManagement.vue'
import Customization from '../views/Customization.vue'
import ExcelExecution from '../views/ExcelExecution.vue'
import KeyMonitor from '../views/KeyMonitor.vue'
import Reports from '../views/Reports.vue'
import ExcelFeatureLayout from '../views/excel/ExcelFeatureLayout.vue'
import ExcelAsrAutomation from '../views/excel/ExcelAsrAutomation.vue'
import { executionState, showBlockNotice } from '../stores/executionStore'
import { i18n } from '../i18n'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/devices',
    name: 'DeviceManagement',
    component: DeviceManagement
  },
  {
    path: '/excel',
    name: 'ExcelDirectory',
    component: ExcelFeatureLayout
  },
  {
    path: '/excel/cases',
    name: 'ExcelExecution',
    component: ExcelExecution
  },
  {
    path: '/excel/asr',
    name: 'ExcelAsrAutomation',
    component: ExcelAsrAutomation
  },
  {
    path: '/keymonitor',
    name: 'KeyMonitor',
    component: KeyMonitor
  },
  {
    path: '/reports',
    name: 'Reports',
    component: Reports
  },
  {
    path: '/customization',
    name: 'Customization',
    component: Customization
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 互斥守卫：图片执行与 ASR 执行不可同时进行。
// 执行中不允许进入另一个模块；/excel 目录页允许进入（另一模块卡片已禁用）。
router.beforeEach((to) => {
  if (executionState.status !== 'running' || !executionState.activeType) {
    return true
  }

  const activeType = executionState.activeType

  const targetModule = to.path.startsWith('/excel/asr')
    ? 'asr'
    : (to.path.startsWith('/excel/cases') ? 'image' : null)

  if (targetModule && targetModule !== activeType) {
    const key = activeType === 'image'
      ? 'executionCard.blockedImageToAsr'
      : 'executionCard.blockedAsrToImage'
    showBlockNotice(i18n.global.t(key))
    return false
  }

  return true
})

export default router

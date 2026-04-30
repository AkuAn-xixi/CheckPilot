import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import DeviceManagement from '../views/DeviceManagement.vue'
import CommandExecution from '../views/CommandExecution.vue'
import Customization from '../views/Customization.vue'
import ExcelExecution from '../views/ExcelExecution.vue'
import KeyMonitor from '../views/KeyMonitor.vue'
import ExcelFeatureLayout from '../views/excel/ExcelFeatureLayout.vue'
import ExcelAsrAutomation from '../views/excel/ExcelAsrAutomation.vue'

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
    path: '/commands',
    name: 'CommandExecution',
    component: CommandExecution
  },
  {
    path: '/excel',
    component: ExcelFeatureLayout,
    children: [
      {
        path: 'cases',
        name: 'ExcelExecution',
        component: ExcelExecution
      },
      {
        path: 'asr',
        name: 'ExcelAsrAutomation',
        component: ExcelAsrAutomation
      }
    ]
  },
  {
    path: '/keymonitor',
    name: 'KeyMonitor',
    component: KeyMonitor
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

export default router

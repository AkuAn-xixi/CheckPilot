import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import DeviceManagement from '../views/DeviceManagement.vue'
import CommandExecution from '../views/CommandExecution.vue'
import ExcelExecution from '../views/ExcelExecution.vue'
import KeyMonitor from '../views/KeyMonitor.vue'

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
    name: 'ExcelExecution',
    component: ExcelExecution
  },
  {
    path: '/keymonitor',
    name: 'KeyMonitor',
    component: KeyMonitor
  }
  
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router

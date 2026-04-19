<template>
  <div class="card">
    <h2 class="mb-4">欢迎使用 ADB 控制工具</h2>
    <p class="mb-6">
      这是一个基于Web的ADB设备控制工具，支持通过命令行和Excel文件执行ADB命令。
    </p>
    
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
      <div class="bg-blue-50 p-4 rounded-lg">
        <h3 class="text-primary mb-2">主要功能</h3>
        <ul class="list-disc pl-5 space-y-1">
          <li>设备管理：查看和选择ADB设备</li>
          <li>命令执行：直接输入和执行命令序列</li>
          <li>Excel执行：从Excel文件中读取和执行命令</li>
          <li>设置管理：配置执行模式和时间控制</li>
        </ul>
      </div>
      
      <div class="bg-green-50 p-4 rounded-lg">
        <h3 class="text-success mb-2">使用指南</h3>
        <ul class="list-disc pl-5 space-y-1">
          <li>首先在设备管理页面选择要控制的ADB设备</li>
          <li>然后在命令执行页面输入命令序列，或在Excel执行页面选择Excel文件</li>
          <li>点击执行按钮开始执行命令</li>
          <li>查看执行结果和日志</li>
        </ul>
      </div>
    </div>
    
    <div class="bg-gray-50 p-4 rounded-lg">
      <h3 class="text-gray-700 mb-2">设备状态</h3>
      <div v-if="devices.length > 0">
        <p class="mb-2">已检测到 {{ devices.length }} 个ADB设备：</p>
        <ul class="list-disc pl-5 space-y-1">
          <li v-for="(device, index) in devices" :key="device">
            {{ index + 1 }}. {{ device }}
            <span v-if="currentDevice === device" class="text-success ml-2">(当前选中)</span>
          </li>
        </ul>
        <router-link to="/devices" class="mt-4 inline-block btn btn-primary">
          管理设备
        </router-link>
      </div>
      <div v-else>
        <p class="text-danger">未检测到ADB设备，请确保设备已连接并开启USB调试模式。</p>
        <router-link to="/devices" class="mt-4 inline-block btn btn-primary">
          刷新设备列表
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

// 状态管理
const devices = ref([])
const currentDevice = ref('')

// 加载设备列表和当前设备
onMounted(async () => {
  await loadDevices()
  await loadCurrentDevice()
})

// 加载设备列表
const loadDevices = async () => {
  try {
    const response = await fetch('/api/devices')
    const data = await response.json()
    devices.value = data.devices
  } catch (error) {
    console.error('获取设备列表失败:', error)
  }
}

// 加载当前设备
const loadCurrentDevice = async () => {
  try {
    const response = await fetch('/api/devices/current')
    const data = await response.json()
    currentDevice.value = data.device
  } catch (error) {
    console.error('获取当前设备失败:', error)
  }
}
</script>

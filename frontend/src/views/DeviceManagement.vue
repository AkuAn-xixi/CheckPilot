<template>
  <div class="card">
    <h2 class="mb-4">设备管理</h2>
    
    <div class="mb-6">
      <button @click="loadDevices" class="btn btn-secondary mb-4">
        刷新设备列表
      </button>
      
      <div v-if="loading">
        <p>加载中...</p>
      </div>
      
      <div v-else-if="devices.length > 0">
        <p class="mb-4">已检测到 {{ devices.length }} 个ADB设备：</p>
        
        <div class="space-y-4">
          <div v-for="(device, index) in devices" :key="device" class="border rounded-lg p-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium">设备 {{ index + 1 }}</p>
                <p class="text-gray-600">{{ device }}</p>
              </div>
              <button 
                @click="selectDevice(index + 1)" 
                class="btn btn-primary"
                :disabled="selectedDevice === device"
              >
                {{ selectedDevice === device ? '已选择' : '选择' }}
              </button>
            </div>
          </div>
        </div>
      </div>
      
      <div v-else>
        <p class="text-danger mb-4">未检测到ADB设备，请确保设备已连接并开启USB调试模式。</p>
        <div class="bg-yellow-50 p-4 rounded-lg">
          <h4 class="font-medium mb-2">排查步骤：</h4>
          <ul class="list-disc pl-5 space-y-1">
            <li>确保设备已通过USB连接到电脑</li>
            <li>在设备上开启USB调试模式</li>
            <li>安装设备驱动程序（如果需要）</li>
            <li>尝试重新连接USB线缆</li>
            <li>重启ADB服务：adb kill-server && adb start-server</li>
          </ul>
        </div>
      </div>
    </div>
    
    <div v-if="selectedDevice" class="bg-green-50 p-4 rounded-lg">
      <h3 class="text-success mb-2">当前选中设备</h3>
      <p>{{ selectedDevice }}</p>
      <p class="text-sm text-gray-600 mt-2">
        设备已成功选择，可以在命令执行或Excel执行页面执行命令。
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

// 状态管理
const devices = ref([])
const selectedDevice = ref('')
const loading = ref(false)

// 加载设备列表和当前设备
onMounted(async () => {
  await loadDevices()
  await loadCurrentDevice()
})

// 加载设备列表
const loadDevices = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/devices')
    const data = await response.json()
    devices.value = data.devices
  } catch (error) {
    console.error('获取设备列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 加载当前设备
const loadCurrentDevice = async () => {
  try {
    const response = await fetch('/api/devices/current')
    const data = await response.json()
    selectedDevice.value = data.device
  } catch (error) {
    console.error('获取当前设备失败:', error)
  }
}

// 选择设备
const selectDevice = async (index) => {
  try {
    const response = await fetch('/api/devices/select', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ device_index: index })
    })
    const data = await response.json()
    selectedDevice.value = data.message.split(': ')[1]
    alert('设备选择成功')
  } catch (error) {
    console.error('选择设备失败:', error)
    alert('选择设备失败，请重试')
  }
}
</script>

<template>
  <div class="card">
    <h2 class="mb-4">{{ $t('deviceManagement.title') }}</h2>
    
    <div class="mb-6">
      <button @click="loadDevices" class="btn btn-secondary mb-4">
        {{ $t('deviceManagement.refresh') }}
      </button>
      
      <div v-if="loading">
        <p>{{ $t('common.loading') }}</p>
      </div>
      
      <div v-else-if="devices.length > 0">
        <p class="mb-4">{{ $t('deviceManagement.detected', { count: devices.length }) }}</p>
        
        <div class="space-y-4">
          <div v-for="(device, index) in devices" :key="device" class="border rounded-lg p-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium">{{ $t('deviceManagement.deviceLabel', { index: index + 1 }) }}</p>
                <p class="text-gray-600">{{ device }}</p>
              </div>
                <button 
                  @click="selectDevice(index)" 
                  class="btn btn-primary"
                  :disabled="selectedDevice === device"
                >
                  {{ selectedDevice === device ? $t('excelAsr.selectedModel') : $t('common.execute') }}
                </button>
            </div>
          </div>
        </div>
      </div>
      
      <div v-else>
        <p class="text-danger mb-4">{{ $t('deviceManagement.noDevices') }}</p>
        <div class="bg-yellow-50 p-4 rounded-lg">
          <h4 class="font-medium mb-2">{{ $t('deviceManagement.troubleshooting') }}</h4>
          <ul class="list-disc pl-5 space-y-1">
            <li>{{ $t('deviceManagement.steps.connect') }}</li>
            <li>{{ $t('deviceManagement.steps.debug') }}</li>
            <li>{{ $t('deviceManagement.steps.driver') }}</li>
            <li>{{ $t('deviceManagement.steps.reconnect') }}</li>
            <li>{{ $t('deviceManagement.steps.restartAdb') }}</li>
          </ul>
        </div>
      </div>
    </div>
    
    <div v-if="selectedDevice" class="bg-green-50 p-4 rounded-lg">
      <h3 class="text-success mb-2">{{ $t('deviceManagement.currentDevice') }}</h3>
      <p>{{ selectedDevice }}</p>
      <p class="text-sm text-gray-600 mt-2">
        {{ $t('deviceManagement.currentDeviceDescription') }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

const DEVICE_STATUS_EVENT = 'checkpilot:device-updated'
// 状态管理
const devices = ref([])
const selectedDevice = ref('')
const loading = ref(false)
const { t } = useI18n({ useScope: 'global' })

const notifyCurrentDeviceChange = (device = selectedDevice.value || '') => {
  window.dispatchEvent(new CustomEvent(DEVICE_STATUS_EVENT, {
    detail: { device }
  }))
}

// 加载设备列表和当前设备
onMounted(async () => {
  await loadDevices()
  await loadCurrentDevice()
})

// 加载设备列表
const loadDevices = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/devices/list')
    const data = await response.json()
    devices.value = Array.isArray(data.devices) ? data.devices : []
  } catch (error) {
    devices.value = []
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
      if (data.status === 'success') {
        selectedDevice.value = data.device || ''
        notifyCurrentDeviceChange()
        alert(t('deviceManagement.alerts.selected'))
      } else {
        alert(t('deviceManagement.alerts.failed', { detail: data.detail || t('deviceManagement.alerts.unknown') }))
      }
  } catch (error) {
    console.error('选择设备失败:', error)
    alert(t('deviceManagement.alerts.retry'))
  }
}
</script>

<template>
  <div class="card">
    <h2 class="mb-4">{{ $t('settings.title') }}</h2>
    
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div class="border rounded-lg p-4">
        <h3 class="font-medium mb-4">{{ $t('settings.execution') }}</h3>
        
        <div class="form-group">
          <label class="form-label">{{ $t('settings.executionMode') }}</label>
          <div class="space-y-2">
            <div class="flex items-center">
              <input 
                type="radio" 
                id="executionModeDirect" 
                v-model="settings.executionMode" 
                value="direct"
                class="mr-2"
              >
              <label for="executionModeDirect">{{ $t('settings.direct') }}</label>
            </div>
            <div class="flex items-center">
              <input 
                type="radio" 
                id="executionModeStep" 
                v-model="settings.executionMode" 
                value="step"
                class="mr-2"
              >
              <label for="executionModeStep">{{ $t('settings.step') }}</label>
            </div>
          </div>
        </div>
        
        <div class="form-group mt-4">
          <label class="form-label">{{ $t('settings.timeControlMode') }}</label>
          <div class="space-y-2">
            <div class="flex items-center">
              <input 
                type="radio" 
                id="timeModeScript" 
                v-model="settings.timeControlMode" 
                value="script"
                class="mr-2"
              >
              <label for="timeModeScript">{{ $t('settings.scriptTime') }}</label>
            </div>
            <div class="flex items-center">
              <input 
                type="radio" 
                id="timeModeGlobal" 
                v-model="settings.timeControlMode" 
                value="global"
                class="mr-2"
              >
              <label for="timeModeGlobal">{{ $t('settings.globalTime') }}</label>
            </div>
          </div>
        </div>
        
        <div class="form-group mt-4" v-if="settings.timeControlMode === 'global'">
          <label class="form-label" for="globalDelay">{{ $t('settings.globalDelay') }}</label>
          <input 
            type="number" 
            id="globalDelay" 
            v-model.number="settings.globalDelay" 
            class="form-input"
            min="0"
            step="0.1"
            :placeholder="$t('settings.globalDelayPlaceholder')"
          >
        </div>
      </div>
      
      <div class="border rounded-lg p-4">
        <h3 class="font-medium mb-4">{{ $t('settings.about') }}</h3>
        
        <div class="space-y-3">
          <div>
            <p class="font-medium">{{ $t('settings.appName') }}</p>
            <p class="text-gray-600">{{ $t('settings.appNameValue') }}</p>
          </div>
          <div>
            <p class="font-medium">{{ $t('settings.version') }}</p>
            <p class="text-gray-600">1.0.0</p>
          </div>
          <div>
            <p class="font-medium">{{ $t('settings.description') }}</p>
            <p class="text-gray-600">{{ $t('settings.descriptionValue') }}</p>
          </div>
          <div>
            <p class="font-medium">{{ $t('settings.features') }}</p>
            <ul class="list-disc pl-5 space-y-1 text-gray-600">
              <li>{{ $t('settings.featureList.devices') }}</li>
              <li>{{ $t('settings.featureList.commands') }}</li>
              <li>{{ $t('settings.featureList.excel') }}</li>
              <li>{{ $t('settings.featureList.executionMode') }}</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
    
    <div class="mt-6 flex justify-end">
      <button @click="saveSettings" class="btn btn-primary">
        {{ $t('settings.saveSettings') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n({ useScope: 'global' })

const settings = ref({
  executionMode: 'direct',
  timeControlMode: 'script',
  globalDelay: 1.0
})

onMounted(() => {
  loadSettings()
})

const loadSettings = () => {
  const savedSettings = localStorage.getItem('adbControlSettings')
  if (savedSettings) {
    try {
      settings.value = JSON.parse(savedSettings)
    } catch (error) {
      console.error(t('settings.alerts.loadFailed'), error)
    }
  }
}

const saveSettings = () => {
  localStorage.setItem('adbControlSettings', JSON.stringify(settings.value))
  alert(t('settings.alerts.saveSuccess'))
}
</script>

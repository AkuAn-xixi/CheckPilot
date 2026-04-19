# ADB 控制工具

基于Web的ADB设备控制工具，支持通过命令行和Excel文件执行ADB命令。

## 功能特性

- **设备管理**：自动检测和列出ADB设备，支持通过序号选择设备
- **命令执行**：支持输入和执行命令序列，显示执行结果
- **Excel执行**：自动列出当前目录下的Excel文件，支持通过序号选择文件，分析文件内容并执行指定行的命令
- **设置管理**：支持配置执行模式和时间控制模式
- **响应式设计**：适配不同屏幕尺寸，提供良好的用户体验
- **错误处理**：对各种错误情况进行了处理，提供友好的错误提示

## 技术栈

- **后端**：FastAPI
- **前端**：Vue.js + Vite + Tailwind CSS
- **ADB**：Android Debug Bridge
- **Excel解析**：pandas

## 安装和部署

### 1. 安装依赖

#### 后端依赖
```bash
pip install fastapi uvicorn pandas openpyxl
```

#### 前端依赖
```bash
cd frontend
npm install
```

### 2. 启动服务

#### 后端服务
```bash
cd backend
python main.py
```

后端服务会在 `http://localhost:8000` 启动。

#### 前端服务
```bash
cd frontend
npm run dev
```

前端服务会在 `http://localhost:3000` 启动。

### 3. 访问应用

在浏览器中打开 `http://localhost:3000` 即可访问ADB控制工具。

## 使用指南

### 1. 设备管理

- 在左侧导航栏点击「设备管理」
- 系统会自动检测并列出已连接的ADB设备
- 点击设备对应的「选择」按钮选择设备
- 选择成功后，设备信息会显示在顶部导航栏

### 2. 命令执行

- 在左侧导航栏点击「命令执行」
- 在命令输入框中输入命令序列，格式为：`KEYNAME/REPEAT/DELAY,KEYNAME/REPEAT/DELAY`
- 例如：`OK/1/1,DOWN/1/1,UP/2/0.5`
- 点击「执行命令」按钮执行命令
- 执行结果会显示在页面下方

### 3. Excel执行

- 在左侧导航栏点击「Excel执行」
- 系统会自动列出当前目录下的Excel文件
- 点击要选择的Excel文件
- 点击「分析文件」按钮分析文件内容
- 系统会显示文件中的有效命令行和跳过的行
- 在「行号」输入框中输入要执行的行号
- 点击「执行」按钮执行命令
- 执行结果会显示在页面下方

### 4. 设置管理

- 在左侧导航栏点击「设置」
- 配置执行模式和时间控制模式
- 点击「保存设置」按钮保存设置

## Excel文件格式

### SmartTV模板格式

支持SmartTV_AutoFullTestCase_TV_Screenshot.xlsx模板格式，要求：

- `runOption` 列为 `Y` 的行会被处理
- 命令可以在 `oriStep` 列或 `preScript` 列中
- 命令格式为：`KEYNAME/REPEAT/DELAY,KEYNAME/REPEAT/DELAY`

### 原始格式

也支持原始格式的Excel文件，要求包含以下列：

- `keyname`：按键名称
- `repeat`：执行次数
- `delay`：延迟时间

## 按键名称

支持的按键名称包括：

- OK, HOME, BACK, UP, DOWN, LEFT, RIGHT, MENU, SETTING
- DIGITAL0-DIGITAL9
- POWER, SOURCE, CHUP, CHDOWN, EXIT
- LIBRARY, TV_AV, VOLUMEUP, VOLUMEDOWN
- NETFLIX, YOUTUBE, PRIME_VII
- ACTIONS, FILES
- RED, GREEN, YELLOW, BLUE
- INFORMATION, MUTE
- APPS

## 常见问题

### 1. 未检测到ADB设备

- 确保设备已通过USB连接到电脑
- 在设备上开启USB调试模式
- 安装设备驱动程序（如果需要）
- 尝试重新连接USB线缆
- 重启ADB服务：`adb kill-server && adb start-server`

### 2. Excel文件未显示

- 确保Excel文件在应用程序所在的目录中
- 支持 .xlsx 和 .xls 格式的文件

### 3. 命令执行失败

- 确保已选择ADB设备
- 检查命令格式是否正确
- 检查按键名称是否存在
- 检查设备是否正常响应

## 打包部署

### 前端打包

```bash
cd frontend
npm run build
```

打包后的文件会在 `frontend/dist` 目录中。

### 后端打包

可以使用 PyInstaller 打包后端：

```bash
pip install pyinstaller
cd backend
pyinstaller --onefile --name adb_controller main.py
```

打包后的可执行文件会在 `backend/dist` 目录中。

## 许可证

MIT

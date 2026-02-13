# 在 Windows 上部署

本指南将帮助您在 Windows 系统上快速部署 LinDream。

## 准备工作

在开始之前，请确保您的系统已安装 **Python 3.8+**。

从 [Python 官网](https://www.python.org/downloads/windows/) 下载并安装。安装时，请务必勾选 "Add Python to PATH" 选项。

## 部署步骤

### 1. 下载源码

访问 LinDream 的 [GitHub 项目页面](https://github.com/DXBbyd/LinDream)，点击右上角的 `<> Code` 按钮，然后选择 `Download ZIP` 下载源码压缩包。

下载完成后，将压缩包解压到一个您喜欢的位置。

### 2. 安装依赖

打开 `cmd` 或 `PowerShell`，并**进入您刚刚解压的项目文件夹**。然后通过创建虚拟环境与 `pip` 一键安装所有 Python 依赖库（使用阿里云镜像加速）：

```powershell
 python -m venv .venv
```

```powershell
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple
```

### 3. 生成配置文件

在同一个终端窗口中，运行项目附带的引导脚本，它会帮助您生成配置文件：

```powershell
python start.py
```

请按照提示输入您的机器人 QQ 号、API Key 等信息。

### 4. 启动项目

一切就绪后，运行以下命令启动 LinDream：

```powershell
python main.py
```

恭喜你已经成功启动了项目，请移步至部署NapCat↓
[napcat](https://napcat.napneko.icu/guide/boot/Shell)
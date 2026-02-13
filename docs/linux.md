# 在 Linux 上部署

本指南将帮助您在 Linux 系统上快速部署 LinDream。

## 准备工作

在开始之前，请确保您的系统已安装 **Python 3.8+** 和 **Git**。

您可以使用包管理器快速安装：

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip git

# CentOS/RHEL
sudo yum install python3 python3-pip git
```

## 部署步骤

### 1. 下载源码

使用 `git` 命令将 LinDream 仓库克隆到您的本地：

```bash
git clone https://github.com/DXBbyd/LinDream.git
cd LinDream
```

::: tip 网络问题？
如果遇到网络问题，可以使用以下镜像站进行下载：
```bash
git clone https://github.fufumc.top/https://github.com/DXBbyd/LinDream.git
```
:::

### 2. 安装依赖

创建虚拟环境并通过 `pip` 一键安装所有 Python 依赖库（使用阿里云镜像加速）：
```bash
 python3 -m venv .venv
 ```
```bash
 source .venv/bin/activate
 ```

```bash
pip3 install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple
```

### 3. 生成配置文件

运行项目附带的引导脚本，它会帮助您生成配置文件：

```bash
python3 start.py
```

请按照提示输入您的机器人 QQ 号、API Key 等信息。

### 4. 启动项目

一切就绪后，运行以下命令启动 LinDream：

```bash
python3 main.py
```

恭喜你已经成功启动了项目，请移步至部署NapCat↓
[napcat](https://napcat.napneko.icu/guide/boot/Shell)
什么？你看不懂嘛？有手把手的教学视频！
[BiliBili](https://www.bilibili.com/video/BV1AHcjzTEwJ/?pop_share=1&spm_id_from=333.40164.0.0&vd_source=0173196d7a2e4755e213b47359712524)
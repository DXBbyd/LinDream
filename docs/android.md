# Android 部署指南

🌐 通过 Termux 运行，支持 ARMv8 设备。

## 下载安装 Termux

本项目支持在两种 Termux 环境中运行，请选择其中一种进行安装：

### 1. ZeroTermux (推荐版本)
ZeroTermux 是一个功能增强的 Termux 分支版本，提供了更好的用户体验。

下载链接：[ZeroTermux v0.118.3.53](https://d.icdown.club/repository/main/ZeroTermux/ZeroTermux-0.118.3.53.apk)

### 2. 官方 Termux
如果您希望使用官方发行版，请访问以下链接获取最新版本。

下载链接：[Termux 官方仓库](https://github.com/termux/termux-app#github)

## 快速配置
安装并启动 Termux 后，按以下步骤操作：

### 1. 修改镜像源
```bash
sed -i 's@^\(deb.*stable main\)$@#\1\ndeb https://mirrors.tuna.tsinghua.edu.cn/termux/termux-packages-24 stable main@' $PREFIX/etc/apt/sources.list && apt update && apt upgrade
```

### 2. 安装依赖
```bash
apt install python git proot-distro python-pip uv -y
```

### 3. 安装容器
```bash
proot-distro install debian
```

### 4. 进入容器
```bash
proot-distro login debian
```

### 5. 切换镜像
```bash
bash <(curl -sSL https://linuxmirrors.cn/main.sh)
```

### 6. 配置镜像源
根据提示选择：阿里云→公网→HTTP→是→否→是

### 7. 克隆项目
```bash
git clone https://github.com/DXBbyd/LinDream.git
```

> [!TIP]
> 如果访问不了 GitHub，可以使用加速镜像：
> ```bash
> git clone http://github.fufumc.top/https://github.com/DXBbyd/LinDream.git
> ```

### 8. 进入项目目录
```bash
cd LinDream
```

### 9. 创建虚拟环境
```bash
uv venv
```

### 10. 安装依赖包
```bash
uv pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple
```

### 11. 启动引导脚本
```bash
uv run start.py
```

### 12. 完成启动
```bash
uv run main.py
```
恭喜你已经成功启动了项目，请移步至部署NapCat↓
[napcat](https://napcat.napneko.icu/guide/boot/Shell)
什么？你看不懂嘛？有手把手的教学视频！
[BiliBili](https://www.bilibili.com/video/BV1AHcjzTEwJ/?pop_share=1&spm_id_from=333.40164.0.0&vd_source=0173196d7a2e4755e213b47359712524)
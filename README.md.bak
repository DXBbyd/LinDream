# LinDream - 砖业的QQ机器人框架

<div align="center">

![LinDream Logo](https://img.shields.io/badge/LinDream-V2.0.2-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.8+-green?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Stable-success?style=for-the-badge)

**一个功能完善、架构清晰、性能优越的QQ机器人框架**

[部署文档，容易爆炸！](https://RBfrom.havugu.cn/docs) · [问题反馈](https://github.com/DXBbyd/LinDream/issues)

</div>

---

## 📖 项目介绍

LinDream 是一个基于 Python 开发的现代化 QQ 机器人框架，采用 WebSocket 协议与 OneBot 协议兼容的 QQ 机器人平台（如 NapCat、go-cqhttp）进行通信。V2.0.1 版本是一次全面的架构重构，从单文件应用转变为砖家级的模块化系统，提供完整的会话管理、插件系统、AI 聊天、权限管理等核心功能。

### ✨ 核心特性

- 🧠 **智能会话管理** - 支持私聊和群聊独立会话，无限对话历史，智能会话切换
- 🔌 **插件化架构** - 完整的插件系统，支持动态加载、依赖管理、数据隔离
- 🤖 **AI 聊天集成** - 集成主流 AI API，支持多人格切换，上下文记忆无限制
- 👥 **精细化权限** - 多级权限系统，支持主人、管理员、用户三级权限控制
- 📊 **性能监控** - 实时性能统计，日志分析，资源使用监控
- 🛡️ **安全审计** - 完整的审计日志系统，内容审核，安全哈希验证
- ⚡ **高性能** - 并发消息处理，智能速率限制，线程池管理

## 🚀 快速开始

### 环境要求

- Python 3.8+
- OneBot 协议兼容的 QQ 机器人平台（推荐 NapCat）

### 部署文档

详细的部署教程、配置说明、插件开发指南请访问：

📖 **[完整部署文档，但是容易爆炸](https://RBfrom.havugu.cn/docs)**
这边建议查看项目目录下docs中的部署文档
[在安卓上部署](https://github.com/DXBbyd/LinDream/docs/android.md)
[在linux上部署](https://github.com/DXBbyd/LinDream/docs/linux.md)
[在Windows上部署](https://github.com/DXBbyd/LinDream/docs/windows.md)
[杂七杂八的配置文件](https://github.com/DXBbyd/LinDream/docs/configuration.md)
---

## 📁 项目结构

```
LinDream/
├── src/                          # 核心业务模块
│   ├── app.py                    # 应用入口
│   ├── bot_manager.py            # 机器人管理器
│   ├── config.py                 # 配置管理器
│   ├── message_handler.py        # 消息处理器
│   ├── room_manager.py           # 会话管理器
│   ├── plugin_base.py            # 插件基类
│   ├── event_bus.py              # 事件总线
│   ├── audit_logger.py           # 审计日志
│   ├── content_moderator.py      # 内容审核
│   ├── performance.py            # 性能监控
│   ├── pipeline.py               # 消息流水线
│   ├── server.py                 # WebSocket 服务器
│   └── message_origin.py         # 消息来源管理
├── modules/                      # 功能模块
│   ├── plugin_system.py          # 插件系统
│   ├── logging.py                # 日志模块
│   ├── rate_limiter.py           # 速率限制器
│   ├── media_handler.py          # 媒体处理器
│   └── __init__.py
├── utils/                        # 工具函数
│   ├── helpers.py                # 辅助函数
│   └── __init__.py
├── data/                         # 数据目录
│   ├── config/                   # 配置文件
│   ├── logs/                     # 日志文件
│   ├── personas/                 # 人格文件
│   ├── room_memories/            # 会话记忆
│   ├── plugin_data/              # 插件数据
│   ├── file/                     # 下载文件
│   └── cache/                    # 缓存文件
├── plugin/                       # 插件目录
├── patches/                      # 补丁目录
├── main.py                       # 主程序
├── requirements.txt              # 依赖列表
├── LICENSE                       # MIT 许可证
└── README.md                     # 项目说明
```

---

## 📖 使用说明

### 基础指令

- `/help` - 显示帮助信息
- `/limit` - 查看当前权限等级
- `/plugin` - 显示已加载的插件列表
- `/persona` - 人格切换管理
- `/room` - 聊天会话管理
- `/stats` - 查看机器人统计信息

### 权限管理（主人）
- `/op` - 设置管理员
- `/deop` - 移除管理员
- `/cfg` - 配置插件

### 插件管理（管理员）
- `/load` - 加载插件
- `/unload` - 卸载插件
- `/reload` - 重载插件

### AI 聊天
- 在群聊中 @机器人并输入消息
- 或使用 `%` 前缀：`%你好，请自我介绍`

---

## 🔧 高级特性

### 会话管理

- **私聊会话**：每个用户独立的私聊会话，支持人格切换和记忆管理
- **群组会话**：每个群组独立的群组会话，支持多人协作
- **会话切换**：智能会话切换，自动管理记忆
- **会话权限**：群组会话创建者拥有完整控制权

### 人格系统

- **多人格支持**：支持多个人格配置，独立记忆
- **人格切换**：私聊随意切换，群组创建者控制
- **记忆隔离**：不同人格的记忆完全独立
- **人格持久化**：重启后自动恢复人格配置

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 📞 联系方式

- **作者**：软白from
- **GitHub**：[DXBbyd](https://github.com/DXBbyd)
- **文档网站**：[https://RBfrom.havugu.cn/docs](https://RBfrom.havugu.cn/docs)

---

## 🙏 致谢

感谢所有为 LinDream 项目做出贡献的开发者和用户！

你的三连就是我坚持的动力喵！ 🎉

---

<div align="center">

**Made with ❤️ by 软白from**

</div>
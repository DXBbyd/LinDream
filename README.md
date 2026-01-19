# LinDream - 砖业的QQ机器人框架

<div align="center">

![LinDream Logo](https://img.shields.io/badge/LinDream-V2.0.1-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.8+-green?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Stable-success?style=for-the-badge)

**一个功能完善、架构清晰、性能优越的QQ机器人框架**

[部署文档](https://RBfrom.havugu.cn/docs) · [插件仓库](https://github.com/DXBbyd/LinDream_plugin) · [问题反馈](https://github.com/DXBbyd/LinDream/issues)

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

---

## 🎉 V2.0.1 重制版重大更新

### 🏗️ 架构重构

#### 模块化架构
- **代码分离**：从 2145 行单文件重构为清晰的模块化架构
  - `src/` - 核心业务模块
  - `modules/` - 功能模块（插件系统、日志、速率限制、媒体处理）
  - `utils/` - 工具函数
- **可维护性**：代码结构清晰，便于维护和扩展
- **可扩展性**：模块化设计，易于添加新功能

#### 会话管理系统升级
- **RoomManager**：引入专业的会话管理器
  - 会话数据持久化到 `data/rooms.json`
  - 会话记忆独立存储在 `data/room_memories/` 文件夹
  - 支持私聊和群聊会话的独立管理
  - 支持会话创建、删除、加入、退出等完整功能

### 🧠 AI 聊天功能重大升级

#### 会话记忆无限制
- **V1.0.2**：有 `session_history_limit` 限制（默认 20 条）
- **V2.0.1**：完全移除记忆限制，支持无限对话历史

#### 智能会话切换
- **切换新会话**：自动清理旧会话记忆
- **私聊→群聊**：保留私聊会话记忆
- **退出群聊**：自动切换回之前的私聊会话

#### 精细化人格权限
- **私聊会话**：可随意切换人格，切换时自动清理全部记忆
- **群组会话**：只能由创建者切换人格（主人和管理员也不行）
- **公平性原则**：实现合理的人格权限控制

### ⚙️ 配置管理升级

#### 结构化配置系统
- `data/config/mainconfig.json` - 主配置
- `data/config/log.json` - 日志配置
- `data/config/runtime_status.json` - 运行时状态
- `data/config/websocket.json` - WebSocket 配置
- 支持配置热重载

#### 性能调优
- 并发消息控制
- 消息速率限制
- 任务超时设置
- 工作线程池管理
- 视频缓存管理

### 🔧 插件系统增强

#### 完整的插件管理系统
- `modules/plugin_system.py` - 插件系统核心
- 支持插件动态加载/卸载
- 插件依赖自动检查和安装
- 插件数据隔离（`data/plugin_data/`）

#### 增强的补丁系统
- 支持补丁元数据
- 补丁配置管理
- 补丁数据隔离

### 📊 日志系统升级

#### 分类日志系统
- `data/logs/system/` - 系统日志
- `data/logs/friend/` - 好友日志
- `data/logs/group/` - 群组日志
- 支持日志轮转和清理

#### 审计系统
- `src/audit_logger.py` - 审计日志模块
- 记录所有关键操作
- 支持安全审计

### 🛡️ 安全性增强

#### 内容审核
- `src/content_moderator.py` - 内容审核模块
- 支持敏感词过滤
- 支持内容安全检查

#### 安全哈希
- `data/config/security_hash.json` - 安全配置
- 支持操作验证

### 🚀 性能优化

#### 并发处理
- 消息队列管理
- 处理锁机制
- 任务信号量控制
- 线程池管理

#### 速率限制
- `modules/rate_limiter.py` - 速率限制器
- 基于会话的速率控制
- 防止消息泛滥

### 📦 数据管理

#### 结构化数据管理
- `data/file/` - 按群组/好友分类存储
- `data/cache/` - 缓存管理
- `data/first-start/` - 首次启动配置

#### 完善的人格系统
- `data/personas/` - 人格文件目录
- 支持多人格切换
- 人格记忆持久化

### 🎯 新增功能

#### 事件总线
- `src/event_bus.py` - 事件驱动架构
- 支持事件发布/订阅
- 模块间解耦

#### 性能监控
- `src/performance.py` - 性能监控模块
- 实时性能统计
- 资源使用监控

#### 媒体处理
- `modules/media_handler.py` - 媒体处理模块
- 统一的媒体文件管理
- 支持多种媒体格式

---

## 🚀 快速开始

### 环境要求

- Python 3.8+
- OneBot 协议兼容的 QQ 机器人平台（推荐 NapCat）

### 部署文档

详细的部署教程、配置说明、插件开发指南请访问：

📖 **[完整部署文档](https://RBfrom.havugu.cn/docs)**

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
- **人格持久化**：重启后自动恢复人格设置

### 插件开发

插件需要实现以下函数之一：
- `on_message(websocket, data, bot_id)` - 处理消息
- `on_command(websocket, data, command, bot_id)` - 处理指令
- `on_load()` - 插件加载时调用

详细的插件开发指南请访问：[插件开发文档](https://RBfrom.havugu.cn/docs/plugin-development)

---

## 📝 版本历史

### V2.0.1 (2026-01-18) - 重制版

#### 🎯 重大更新
- **架构重构**：从单文件应用转变为模块化架构
- **会话管理**：引入 RoomManager，支持完整的会话管理功能
- **AI 聊天升级**：无限对话历史，智能会话切换
- **插件系统增强**：完整的插件管理系统，支持依赖管理
- **性能优化**：并发处理，速率限制，性能监控
- **安全增强**：内容审核，审计日志，安全哈希

#### 🆕 新增功能
- 事件总线系统
- 性能监控模块
- 媒体处理模块
- 审计日志系统
- 内容审核模块

#### 🔧 功能优化
- 配置管理系统升级
- 日志系统分类
- 数据管理结构化
- 人格系统完善

#### 🐛 问题修复
- 修复群聊人格管理问题
- 优化消息解析逻辑
- 改进私聊响应策略

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来改进项目！

### 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

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
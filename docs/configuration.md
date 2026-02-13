# JSON参数说明

LinDream 提供了灵活且强大的配置系统，所有配置文件均位于安装目录下的 `config/` 文件夹（或根目录，视部署方式而定）。

::: tip 提示
修改配置文件后，通常需要**重启 LinDream** 才能生效。
:::

## 消息平台配置

为了让消息平台（如 NapCat）与 LinDream 通信，您需要将消息平台配置为 **WebSocket 客户端**，并连接到 LinDream 开启的 WebSocket 服务。

以 **NapCat** 为例：

1.  在 NapCat 的配置中，找到 **WebSocket** 相关设置。
2.  将其配置为 **正向反向代理** 模式。
3.  连接地址（URL）应填写为：
    ```
    ws://<IP>:<端口>
    ```
    其中 `<IP>` 和 `<端口>` 对应 LinDream 配置文件 `mainconfig.json` 中的 `websocket.host` 和 `websocket.port`。

    **默认情况下，连接地址为：**
    ```
    ws://127.0.0.1:2048
    ```

::: warning 重要警告
**请勿在 NapCat 的 WebSocket 配置中设置 Token（访问令牌）**，否则将导致连接失败。
:::

---

## 核心配置：mainconfig.json

这是 LinDream 的“大脑”，控制着机器人连接、AI、性能与安全策略。

```json
{
  "bot_id": "177141909",
  "websocket": {
    "host": "127.0.0.1",
    "port": 2048,
    "max_connections": 100
  },
  "logging": {
    "level": "INFO",
    "max_files": 100,
    "compression": true,
    "formats": {
      "system": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
      "friend": "%(asctime)s - %(message)s",
      "group": "%(asctime)s - %(message)s"
    }
  },
  "download": {
    "max_workers": 3
  },
  "performance": {
    "max_concurrent_messages": 50,
    "message_rate_limit": 10,
    "task_timeout": 30,
    "max_worker_threads": 10,
    "max_video_cache_size": 10,
    "message_cache_size": 1000,
    "session_history_limit": 114514,
    "video_cleanup_delay": 300
  },
  "ai_config": {
    "api_key": "sk-********************************",
    "api_url": "https://api.example.com/chat/completions",
    "model_name": "gpt-4"
  },
  "security": {
    "content_moderation": {
      "enabled": true,
      "baidu_api_key": "",
      "blacklist_keywords": [],
      "whitelist_keywords": []
    },
    "audit_log": {
      "enabled": true,
      "log_file": "data/logs/audit.log",
      "max_file_size": 10485760
    }
  },
  "owners": [
    "3157037483"
  ]
}
```

### 字段详解

| 模块 | 字段 | 说明 |
| :--- | :--- | :--- |
| **基础** | `bot_id` | 机器人 QQ 号，用于标识身份。 |
| | `owners` | **超级管理员列表**。填入 QQ 号，拥有最高权限（如远程关机、执行 Shell）。 |
| **WebSocket** | `host` | 监听地址。`127.0.0.1` 仅允许本机连接；`0.0.0.0` 允许外网连接。 |
| | `port` | 监听端口，默认为 `2048`。 |
| **AI (ai_config)** | `api_key` | OpenAI 格式的 API 密钥。 |
| | `api_url` | 接口地址，支持第三方中转（One API 等）。 |
| | `model_name` | 使用的模型名称，如 `gpt-4`, `gpt-3.5-turbo`。 |
| **性能** | `max_concurrent_messages` | 最大并发消息处理数，防止高频刷屏卡死。 |
| | `session_history_limit` | 上下文记忆长度限制。 |
| | `video_cleanup_delay` | 视频缓存自动清理时间（秒）。 |
| **安全** | `content_moderation` | 内容审查配置，支持百度 API 或本地黑名单。 |

---

## 自动生成文件 (勿动)

以下文件由系统自动维护，**请勿手动修改**，否则可能导致系统异常。

### 1. runtime_status.json
记录系统运行状态，如上次关机时间、日志加密状态。

```json
{
  "last_shutdown": "2026-01-16T20:01:25.786204",
  "logs_encrypted": true,
  "system_status": "normal"
}
```

### 2. security_hash.json
存储安全校验哈希值，用于验证文件完整性或密码校验。

```json
{
  "password_hash": "384fde3636e6e01e0194d297...",
  "created_at": "2026-01-16T20:01:25.788185"
}
```

---

## 日志配置 (log.json)

如果您需要单独调整日志策略，可参考此文件结构。通常这部分内容已包含在 `mainconfig.json` 中。

- `level`: 日志等级，推荐 `INFO`，调试时可改为 `DEBUG`。
- `compression`: 是否压缩旧日志文件（节省空间）。
# LinDream 插件系统文档

## 概述

LinDream 插件系统已完全重写，基于插件系统设计提示词实现，提供了强大的插件开发能力和 AI Tool 集成。

## 新特性

### 1. 插件系统

- **基于类的插件架构**：所有插件继承 `PluginBase` 类
- **依赖管理**：自动解析和加载依赖关系
- **生命周期管理**：完整的插件加载、卸载、启用、禁用流程
- **命令系统**：支持命令注册和处理
- **事件系统**：支持事件订阅和发布

### 2. Tool 系统

- **AI 可调用工具**：插件可以注册工具供 AI 调用
- **Tool Loop Agent**：自动处理工具调用和 LLM 请求的循环
- **OpenAI 格式兼容**：工具定义兼容 OpenAI Function Calling 格式
- **类型安全**：支持参数类型验证和枚举值检查

### 3. 事件系统

- **优先级支持**：事件处理器可以设置优先级
- **事件传播控制**：支持停止事件传播
- **异步处理**：完全异步的事件处理

## 插件开发

### 插件结构

```
plugin/
├── your_plugin/
│   ├── main.py          # 插件主文件
│   ├── metadata.yaml    # 插件元数据
│   └── requirements.txt # 依赖文件（可选）
```

### metadata.yaml 格式

```yaml
id: plugin_id
name: 插件名称
version: "1.0.0"
author: 作者名
description: 插件描述
repository: https://github.com/your/plugin
dependencies: []  # 依赖的其他插件ID
required_permissions: []  # 需要的权限
```

### 插件示例

```python
from modules.plugin_system.core import PluginBase, PluginMetadata, ToolParameter

class MyPlugin(PluginBase):
    def __init__(self, context):
        super().__init__(context)
        self.name = "my_plugin"
        self.version = "1.0.0"
        self.author = "Your Name"
        self.description = "我的插件"
        
        # 注册命令和工具
        self._register_commands()
        self._register_tools()
    
    @property
    def plugin_info(self) -> PluginMetadata:
        return PluginMetadata(
            id="my_plugin",
            name=self.name,
            version=self.version,
            author=self.author,
            description=self.description
        )
    
    async def on_load(self):
        """插件加载时调用"""
        await super().on_load()
        print("插件已加载")
    
    async def on_message(self, message_data: dict) -> str:
        """处理消息"""
        # 处理消息逻辑
        return None
    
    async def on_command(self, command: str, args: list, context: dict) -> str:
        """处理命令"""
        if command == "hello":
            return "你好！"
        return None
```

## Tool 开发

### 注册工具

```python
from modules.plugin_system.core import ToolDefinition, ToolParameter

def _register_tools(self):
    if not self.context.tool_system:
        return
    
    tool = ToolDefinition(
        name="my_tool",
        description="工具描述",
        parameters=[
            ToolParameter(
                name="param1",
                type="string",
                description="参数描述",
                required=True
            ),
            ToolParameter(
                name="param2",
                type="integer",
                description="可选参数",
                required=False,
                default=10
            )
        ],
        handler=self._my_tool_handler,
        timeout=30
    )
    
    self.context.tool_system.register_tool(tool)
```

### 工具处理器

```python
async def _my_tool_handler(self, arguments: dict, context: dict) -> dict:
    """
    工具处理器
    
    Args:
        arguments: 工具参数
        context: 上下文信息
        
    Returns:
        执行结果字典
    """
    param1 = arguments.get("param1", "")
    param2 = arguments.get("param2", 10)
    
    # 执行工具逻辑
    result = {
        "param1": param1,
        "param2": param2,
        "result": param1 * param2
    }
    
    return result
```

### AI 调用工具

AI 会自动检测可用的工具，并在需要时调用。工具会以 OpenAI Function Calling 的格式呈现给 AI。

## 命令系统

### 注册命令

```python
def _register_commands(self):
    self._command_handlers = {}
    self._register_command("hello", self._handle_hello, "打招呼")
    self._register_command("echo", self._handle_echo, "回声")

def _register_command(self, name: str, handler, description: str):
    command_handler = CommandHandler(name, handler, description)
    self._command_handlers[name] = command_handler
```

### 使用命令

用户可以通过 `/command` 格式调用插件命令：
```
/hello
/echo 你好世界
```

## 事件系统

### 订阅事件

```python
async def on_load(self):
    await super().on_load()
    
    # 订阅事件
    self.context.subscribe_event("message", self._on_message_event, priority=10)

async def _on_message_event(self, event):
    """事件处理器"""
    print(f"收到事件: {event.data}")
```

### 发布事件

```python
await self.context.publish_event("custom_event", {"data": "value"})
```

## 插件上下文

插件上下文提供了以下功能：

- `send_message()`: 发送消息
- `get_config()`: 获取配置
- `set_config()`: 设置配置
- `subscribe_event()`: 订阅事件
- `unsubscribe_event()`: 取消订阅事件
- `publish_event()`: 发布事件
- `register_tool()`: 注册工具
- `unregister_tool()`: 注销工具
- `get_plugin_data_dir()`: 获取插件数据目录

## 迁移指南

### 从旧插件系统迁移

1. 创建 `metadata.yaml` 文件
2. 将插件类继承 `PluginBase`
3. 将 `on_message` 函数改为异步
4. 使用新的上下文 API
5. 可选：注册 Tool 供 AI 调用

### 从 Skill 系统迁移到 Tool 系统

1. 将 Skill 的 `execute` 函数改为 Tool 处理器
2. 使用 `ToolDefinition` 和 `ToolParameter` 定义工具
3. 注册到 `tool_system`
4. AI 会自动调用工具，无需手动解析

## 示例插件

项目包含以下示例插件：

1. **example_plugin**: 基础插件示例
2. **tools_example**: Tool 系统示例

查看这些插件的源代码以了解更多细节。

## 注意事项

1. 所有处理函数都是异步的，使用 `async/await`
2. 不要在插件中使用阻塞操作
3. 使用 `aiohttp` 或 `httpx` 进行网络请求
4. 插件数据应存储在 `data/plugin_data/{plugin_id}_data/` 目录
5. 使用 `requirements.txt` 声明依赖

## 支持

如有问题，请查看示例插件或提交 Issue。
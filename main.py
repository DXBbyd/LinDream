#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import websockets
import json
import datetime
from colorama import init, Fore
import os
import httpx
import random

# =========================
# 初始化 colorama
# =========================
init(autoreset=True)

# =========================
# 工具函数
# =========================
def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 图片/视频路径（主程序在 LinDream）
IMAGE_DIR = os.path.join("file", "picture")
VIDEO_DIR = os.path.join("file", "video")
LOG_FILE = "message_log.txt"
AUTO_REPLY_FILE = "auto.txt"
RANDOM_REPLY_FILE = "random.txt"
PLUGIN_DIR = "plugin"  # 插件目录

os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(PLUGIN_DIR, exist_ok=True)

# 配置变量
BOT_ID = None
MAX_DOWNLOAD_WORKERS = 3

# 自动回复规则和随机回复
auto_reply_rules = {}
random_replies = []

# 会话管理
user_sessions = {}  # {user_id: session_data}
group_sessions = {}  # {group_id: session_data}
current_persona = "default"

# 插件系统
loaded_plugins = []

# 消息缓存 + 下载队列
message_cache = {}
download_queue = asyncio.Queue()
video_cleanup_tasks = []

# =========================
# 插件系统
# =========================
def load_plugins():
    """加载所有插件"""
    global loaded_plugins
    loaded_plugins = []
    
    if not os.path.exists(PLUGIN_DIR):
        log_platform_info("插件目录不存在，跳过插件加载")
        return
    
    try:
        for plugin_name in os.listdir(PLUGIN_DIR):
            plugin_path = os.path.join(PLUGIN_DIR, plugin_name)
            if os.path.isdir(plugin_path):
                main_file = os.path.join(plugin_path, "main.py")
                if os.path.exists(main_file):
                    try:
                        # 动态导入插件
                        import importlib.util
                        spec = importlib.util.spec_from_file_location(f"plugin_{plugin_name}", main_file)
                        plugin_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(plugin_module)
                        
                        # 检查插件是否有必要的函数
                        if hasattr(plugin_module, 'on_message') or hasattr(plugin_module, 'on_load') or hasattr(plugin_module, 'on_command'):
                            # 获取插件的自定义触发指令
                            plugin_cmd = getattr(plugin_module, 'plugin_cmd', None)
                            
                            loaded_plugins.append({
                                'name': plugin_name,
                                'module': plugin_module,
                                'path': plugin_path,
                                'cmd': plugin_cmd  # 添加插件自定义触发指令
                            })
                            
                            # 调用插件加载函数（如果存在）
                            if hasattr(plugin_module, 'on_load'):
                                plugin_module.on_load()
                                
                            log_platform_info(f"已加载插件: {plugin_name}" + (f" (触发指令: {plugin_cmd})" if plugin_cmd else ""))
                        else:
                            log_platform_info(f"插件 {plugin_name} 缺少必要函数，跳过加载")
                    except Exception as e:
                        log_platform_info(f"加载插件 {plugin_name} 失败: {e}")
    except Exception as e:
        log_platform_info(f"扫描插件目录失败: {e}")
    
    # 为插件帮助系统设置插件列表
    for plugin_info in loaded_plugins:
        if plugin_info['name'] == 'plugin_help' and hasattr(plugin_info['module'], 'set_main_plugins'):
            try:
                plugin_info['module'].set_main_plugins(loaded_plugins)
            except Exception as e:
                log_platform_info(f"为插件帮助系统设置插件列表失败: {e}")

async def handle_plugin_messages(websocket, data):
    """处理插件消息"""
    # 首先让插件检查是否需要处理此消息（插件可以自定义触发指令）
    for plugin_info in loaded_plugins:
        try:
            plugin_module = plugin_info['module']
            if hasattr(plugin_module, 'on_message'):
                # 调用插件的消息处理函数
                result = plugin_module.on_message(websocket, data, BOT_ID)
                # 如果插件返回True，表示消息已被处理
                if result:
                    return True
        except Exception as e:
            log_platform_info(f"插件 {plugin_info['name']} 处理消息时出错: {e}")
    
    # 检查是否@机器人并包含插件调用格式（保留旧的插件调用方式作为备选）
    if data.get("message_type") == "group":
        message_content = format_message(data.get("message")).strip()
        
        # 检查是否@了机器人
        is_at_bot = False
        for msg_item in data.get("message", []):
            if msg_item.get("type") == "at" and str(msg_item.get("data", {}).get("qq", "")) == str(BOT_ID):
                is_at_bot = True
                break
        
        # 如果@了机器人且消息包含插件调用格式
        if is_at_bot and message_content.startswith("plugin/"):
            # 解析插件调用格式: plugin/插件名/指令
            parts = message_content.split("/", 2)
            if len(parts) >= 2:
                plugin_name = parts[1]
                
                # 尝试找到并调用指定插件
                for plugin_info in loaded_plugins:
                    if plugin_info['name'] == plugin_name:
                        try:
                            plugin_module = plugin_info['module']
                            if hasattr(plugin_module, 'on_command'):
                                # 调用插件的命令处理函数
                                command = parts[2] if len(parts) > 2 else ""
                                result = plugin_module.on_command(websocket, data, command, BOT_ID)
                                if result:
                                    return True
                        except Exception as e:
                            log_platform_info(f"插件 {plugin_name} 处理命令时出错: {e}")
                            return True  # 防止继续处理
    
    return False

# =========================
# 文件日志写入
# =========================
def write_log(text):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")

# =========================
# 下载文件
# =========================
async def download_file(url, path):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code == 200:
                with open(path, "wb") as f:
                    f.write(response.content)
                return True
    except Exception as e:
        log_platform_info(f"下载失败: {url}, 错误: {e}")
    return False

async def schedule_video_cleanup(path, delay=600):
    await asyncio.sleep(delay)
    if os.path.exists(path):
        os.remove(path)
        msg = f"[通信信息] 已清理视频: {path}"
        print(Fore.LIGHTCYAN_EX + msg)
        write_log(msg)

# =========================
# 异步下载队列处理
# =========================
async def download_worker():
    while True:
        url, file_type, filename = await download_queue.get()
        full_path = os.path.join(IMAGE_DIR if file_type=="image" else VIDEO_DIR, filename)
        if await download_file(url, full_path):
            msg = f"{file_type.capitalize()}已下载: {full_path}" + ("（10分钟后清理）" if file_type=="video" else "")
            log_platform_info(msg)
            if file_type=="video":
                cleanup_task = asyncio.create_task(schedule_video_cleanup(full_path))
                video_cleanup_tasks.append(cleanup_task)
        download_queue.task_done()

# =========================
# 发送消息
# =========================
async def send_message(websocket, message, group_id=None, user_id=None):
    try:
        msg_data = {
            "action": "send_group_msg" if group_id else "send_private_msg",
            "params": {}
        }
        
        if group_id:
            msg_data["params"]["group_id"] = group_id
        else:
            msg_data["params"]["user_id"] = user_id
            
        msg_data["params"]["message"] = message
        
        await websocket.send(json.dumps(msg_data))
        return True
    except Exception as e:
        log_platform_info(f"发送消息失败: {e}")
        return False

# =========================
# 格式化消息
# =========================
def format_message(msg):
    if isinstance(msg, list):
        parts = []
        for m in msg:
            tp = m.get("type")
            data = m.get("data", {})

            if tp == "text":
                parts.append(data.get("text", ""))
            elif tp == "at":
                parts.append(f"@{data.get('qq','未知')} ")
            elif tp == "reply":
                parts.append(f"[引用:{data.get('id','未知')}]")
            elif tp == "image":
                parts.append(f"[图片] {data.get('url') or data.get('file','')}")
            elif tp == "json":
                try:
                    inner = json.loads(data.get("data","{}"))
                    meta = inner.get("meta", {}).get("contact", {})
                    nickname = meta.get("nickname","")
                    tag = meta.get("tag","")
                    jump = meta.get("jumpUrl","")
                    parts.append(f"[JSON卡片] {nickname} | {tag} | {jump}")
                except:
                    parts.append("[JSON卡片]")
            else:
                parts.append(f"[{tp}]")
        return "".join(parts)
    elif isinstance(msg, dict):
        return json.dumps(msg, ensure_ascii=False)
    else:
        return str(msg)

# =========================
# 日志输出
# =========================
def log_system_event(data):
    text = f"[系统消息] {now()} | {data.get('meta_event_type')} ({data.get('sub_type','')})"
    print(Fore.LIGHTGREEN_EX + text)
    write_log(text)

def log_platform_info(text):
    msg = f"[平台信息] {now()} | {text}"
    print(Fore.LIGHTYELLOW_EX + msg)
    write_log(msg)

def log_communication(data, media_files=None, is_bot_message=False):
    t = datetime.datetime.fromtimestamp(data["time"]).strftime("%H:%M:%S")
    sender = data.get("sender", {})
    user_name = sender.get("nickname","未知")
    user_id = sender.get("user_id")
    
    # 如果是机器人消息，添加标识
    if is_bot_message:
        user_name = f"[机器人]{user_name}"
    
    msg_text = format_message(data.get("message"))
    media_str = f" | 下载文件: {', '.join(media_files)}" if media_files else ""
    if data.get("message_type")=="group":
        group_name = data.get("group_name","未知群")
        group_id = data.get("group_id")
        msg = f"[通信信息] {t} | 群:{group_name}({group_id}) | 来自:{user_name}({user_id}) | 内容:{msg_text}{media_str}"
    else:
        msg = f"[通信信息] {t} | 私聊来自:{user_name}({user_id}) | 内容:{msg_text}{media_str}"
    print(Fore.LIGHTCYAN_EX + msg)
    write_log(msg)  # 日志也写入下载文件信息

def log_recall(data):
    msg_id = data.get("message_id") or data.get("msg_id")
    cached = message_cache.get(msg_id)
    if cached:
        text = format_message(cached.get("message"))
    else:
        text = "[无法获取内容]"
    msg = f"[反撤回] 群:{data.get('group_id')} | 用户:{data.get('user_id')} | 操作者:{data.get('operator_id')} | 内容:{text}"
    print(Fore.LIGHTRED_EX + msg)
    write_log(msg)

# =========================
# 处理媒体文件（加入下载队列，生成自定义文件名）
# =========================
async def handle_media(msg, group_name="", group_id="", sender_name="", sender_id=""):
    media_files = []
    for m in msg:
        if m.get("type") in ["image", "video"]:
            url = m.get("data", {}).get("url")
            if url:
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                ext = ".jpg" if m["type"]=="image" else ".mp4"
                safe_group = group_name.replace("/", "_").replace("\\", "_")
                safe_user = sender_name.replace("/", "_").replace("\\", "_")
                filename = f"{timestamp}_{safe_group}({group_id})_{safe_user}({sender_id}){ext}"
                download_queue.put_nowait((url, m["type"], filename))
                media_files.append(filename)
    return media_files

# =========================
# 加载自动回复规则
# =========================
def load_auto_reply_rules():
    global auto_reply_rules
    auto_reply_rules = {}
    
    if os.path.exists(AUTO_REPLY_FILE):
        try:
            with open(AUTO_REPLY_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and " " in line:
                        keyword, reply = line.split(" ", 1)
                        auto_reply_rules[keyword] = reply
            log_platform_info(f"已加载 {len(auto_reply_rules)} 条自动回复规则")
        except Exception as e:
            log_platform_info(f"加载自动回复规则失败: {e}")

# =========================
# 加载随机回复内容
# =========================
def load_random_replies():
    global random_replies
    random_replies = []
    
    if os.path.exists(RANDOM_REPLY_FILE):
        try:
            with open(RANDOM_REPLY_FILE, "r", encoding="utf-8") as f:
                random_replies = [line.strip() for line in f if line.strip()]
            log_platform_info(f"已加载 {len(random_replies)} 条随机回复")
        except Exception as e:
            log_platform_info(f"加载随机回复失败: {e}")

# =========================
# 处理自动回复
# =========================
async def handle_auto_reply(websocket, data):
    # 只处理群消息和私聊消息
    if data.get("post_type") != "message":
        # 让插件处理非消息事件
        await handle_plugin_messages(websocket, data)
        return
        
    # 不处理机器人自己发送的消息
    sender = data.get("sender", {})
    sender_id = sender.get("user_id")
    if str(sender_id) == str(BOT_ID):
        return
        
    # 首先让插件处理消息
    if await handle_plugin_messages(websocket, data):
        return  # 插件已处理消息，不再继续处理
        
    # 首先尝试处理指令
    config_file = "config.json"
    config_data = {}
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except:
            pass
    
    # 检查是否@机器人或使用指令前缀
    message_content = format_message(data.get("message")).strip()
    is_at_bot = False
    is_command_prefix = False
    is_ai_prefix = False  # 新增AI前缀标志
    
    # 检查是否@机器人
    if data.get("message_type") == "group":
        for msg_item in data.get("message", []):
            if msg_item.get("type") == "at" and str(msg_item.get("data", {}).get("qq", "")) == str(BOT_ID):
                is_at_bot = True
                break
    
    # 检查是否使用指令前缀
    if message_content.startswith("/"):
        is_command_prefix = True
    
    # 检查是否使用AI前缀
    if message_content.startswith("%"):
        is_ai_prefix = True
    
    # 如果是@机器人或使用指令前缀，则处理指令
    if is_at_bot or is_command_prefix:
        # 如果是指令消息，处理后返回
        if await handle_commands(websocket, data, config_data):
            return
    # 如果不是指令触发条件但使用了AI前缀，触发AI聊天
    elif is_ai_prefix:
        # 提取%后的内容
        ai_content = message_content[1:].strip()  # 去掉%并去除首尾空格
        if ai_content:
            api_key = config_data.get("api_key", "")
            api_url = config_data.get("api_url", "https://apis.iflow.cn/v1/chat/completions")
            model_name = config_data.get("model_name", "qwen3-coder-plus")
            if api_key:
                # 获取会话
                sender = data.get("sender", {})
                sender_id = sender.get("user_id")
                if data.get("message_type") == "group":
                    session = get_group_session(data.get("group_id"))
                else:
                    session = get_user_session(sender_id)
                
                ai_response = await chat_with_ai(ai_content, api_key, api_url, model_name, session)
                if ai_response:
                    # 更新会话历史
                    update_session_history(session, ai_content, ai_response)
                    
                    group_id = data.get("group_id")
                    user_id = sender_id
                    await send_message(websocket, ai_response, group_id=group_id, user_id=user_id if not group_id else None)
                    log_platform_info(f"AI回复: {ai_response}")
                    return
    # 如果不是指令或AI前缀，进行关键词匹配等
    else:
        # 获取消息内容
        message_content = format_message(data.get("message")).strip()
        
        # 检查关键词自动回复（绝对匹配）
        for keyword, reply in auto_reply_rules.items():
            # 绝对匹配：消息内容完全等于关键词
            if message_content == keyword:
                # 发送回复
                if data.get("message_type") == "group":
                    await send_message(websocket, reply, group_id=data.get("group_id"))
                else:
                    await send_message(websocket, reply, user_id=data.get("sender", {}).get("user_id"))
                log_platform_info(f"触发关键词回复: {keyword} -> {reply}")
                return
        
        # 检查是否@机器人（随机回复）
        if data.get("message_type") == "group":
            for msg_item in data.get("message", []):
                if msg_item.get("type") == "at" and str(msg_item.get("data", {}).get("qq", "")) == str(BOT_ID):
                    # @了机器人，随机回复
                    if random_replies:
                        reply = random.choice(random_replies)
                        await send_message(websocket, reply, group_id=data.get("group_id"))
                        log_platform_info(f"触发@随机回复: {reply}")
                    return
    
    # 获取消息内容
    message_content = format_message(data.get("message")).strip()
    
    # 检查关键词自动回复（绝对匹配）
    for keyword, reply in auto_reply_rules.items():
        # 绝对匹配：消息内容完全等于关键词
        if message_content == keyword:
            # 发送回复
            if data.get("message_type") == "group":
                await send_message(websocket, reply, group_id=data.get("group_id"))
            else:
                await send_message(websocket, reply, user_id=data.get("sender", {}).get("user_id"))
            log_platform_info(f"触发关键词回复: {keyword} -> {reply}")
            return
    
    # 检查是否@机器人（随机回复）
    if data.get("message_type") == "group":
        for msg_item in data.get("message", []):
            if msg_item.get("type") == "at" and str(msg_item.get("data", {}).get("qq", "")) == str(BOT_ID):
                # @了机器人，随机回复
                if random_replies:
                    reply = random.choice(random_replies)
                    await send_message(websocket, reply, group_id=data.get("group_id"))
                    log_platform_info(f"触发@随机回复: {reply}")
                return

# =========================
# 权限检查
# =========================
def get_user_permission_level(user_id, config_data):
    """获取用户权限等级：3-主人，2-管理员，1-用户，0-无权限"""
    owner_id = config_data.get("owner_id")
    admins = config_data.get("admins", [])
    users = config_data.get("users", [])
    
    if str(user_id) == str(owner_id):
        return 3  # 主人
    elif user_id in admins:
        return 2  # 管理员
    elif user_id in users or str(user_id) in users:
        return 1  # 用户
    else:
        return 1  # 默认为用户权限

def is_authorized(user_id, required_level, config_data):
    """检查用户是否有足够权限"""
    user_level = get_user_permission_level(user_id, config_data)
    return user_level >= required_level

# =========================
# 会话管理
# =========================
def get_user_session(user_id):
    """获取用户会话"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "history": [],
            "persona": "default"
        }
    return user_sessions[user_id]

def get_group_session(group_id):
    """获取群聊会话"""
    if group_id not in group_sessions:
        group_sessions[group_id] = {
            "history": [],
            "persona": "default"
        }
    return group_sessions[group_id]

def update_session_history(session, user_message, ai_response):
    """更新会话历史"""
    session["history"].append({"user": user_message, "ai": ai_response})
    # 限制历史记录长度
    if len(session["history"]) > 10:
        session["history"] = session["history"][-10:]

# =========================
# 人格管理
# =========================
def load_persona(persona_name):
    """加载指定人格配置"""
    persona_file = os.path.join("persona", f"{persona_name}.txt")
    if os.path.exists(persona_file):
        try:
            with open(persona_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            log_platform_info(f"加载人格文件失败: {e}")
    return None

def list_personas():
    """列出所有可用的人格"""
    personas = []
    if os.path.exists("persona"):
        try:
            for file in os.listdir("persona"):
                if file.endswith(".txt"):
                    personas.append(file[:-4])  # 去掉.txt后缀
        except Exception as e:
            log_platform_info(f"列出人格文件失败: {e}")
    return personas

# =========================
# AI聊天功能
# =========================
async def chat_with_ai(message, api_key, api_url, model_name, session=None):
    """与AI进行对话"""
    if not api_key:
        return None
        
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 构建消息历史
        messages = []
        
        # 如果有会话历史，添加到消息中
        if session and session.get("history"):
            for interaction in session["history"]:
                messages.append({"role": "user", "content": interaction["user"]})
                messages.append({"role": "assistant", "content": interaction["ai"]})
        
        # 添加当前消息
        messages.append({"role": "user", "content": message})
        
        # 如果有特定人格，添加人格提示
        if session and session.get("persona") and session["persona"] != "default":
            persona_content = load_persona(session["persona"])
            if persona_content:
                messages.insert(0, {"role": "system", "content": persona_content})
        
        data = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.7
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, headers=headers, json=data, timeout=30.0)
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                log_platform_info(f"AI聊天API错误: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        log_platform_info(f"AI聊天功能异常: {e}")
        return None

# =========================
# 指令处理
# =========================
async def handle_commands(websocket, data, config_data):
    """处理指令消息"""
    # 只处理群消息和私聊消息
    if data.get("post_type") != "message":
        return False
        
    # 不处理机器人自己发送的消息
    sender = data.get("sender", {})
    sender_id = sender.get("user_id")
    if str(sender_id) == str(BOT_ID):
        return False
    
    # 提取消息文本
    message_content = format_message(data.get("message")).strip()
    
    # 检查是否@机器人
    is_at_bot = False
    if data.get("message_type") == "group":
        for msg_item in data.get("message", []):
            if msg_item.get("type") == "at" and str(msg_item.get("data", {}).get("qq", "")) == str(BOT_ID):
                is_at_bot = True
                break
    
    # 如果@了机器人，直接进行AI聊天
    if is_at_bot:
        # 提取@机器人后的文本内容
        chat_content = ""
        for msg_item in data.get("message", []):
            if msg_item.get("type") == "text":
                text = msg_item.get("data", {}).get("text", "").strip()
                if text:
                    chat_content = text
                    break
        
        if chat_content:
            # 检查是否是指令
            first_word = chat_content.split()[0] if chat_content.split() else ""
            if first_word in ["/help", "/limit", "/op", "/reop", "/reset", "/cmd", "help", "limit", "op", "reop", "reset", "cmd", "/persona", "/listpersona", "/personality", "/plugin"]:
                # 这是指令，按指令处理
                pass
            else:
                # 这是AI聊天
                api_key = config_data.get("api_key", "")
                api_url = config_data.get("api_url", "https://apis.iflow.cn/v1/chat/completions")
                model_name = config_data.get("model_name", "qwen3-coder-plus")
                if api_key:
                    # 获取会话
                    if data.get("message_type") == "group":
                        session = get_group_session(data.get("group_id"))
                    else:
                        session = get_user_session(sender_id)
                    
                    ai_response = await chat_with_ai(chat_content, api_key, api_url, model_name, session)
                    if ai_response:
                        # 更新会话历史
                        update_session_history(session, chat_content, ai_response)
                        
                        group_id = data.get("group_id")
                        user_id = sender_id
                        await send_message(websocket, ai_response, group_id=group_id, user_id=user_id if not group_id else None)
                        log_platform_info(f"AI回复: {ai_response}")
                        return True
                return True  # 已处理，即使没有API密钥
    
    # 检查是否以/开头的指令
    elif message_content.startswith("/"):
        first_word = message_content.split()[0] if message_content.split() else ""
        if first_word in ["/help", "/limit", "/op", "/reop", "/reset", "/cmd", "/persona", "/listpersona", "/personality", "/plugin"]:
            # 这是指令，按指令处理
            pass
        else:
            # 以/开头但不是已知指令，不处理
            return False
    
    # 处理明确的指令
    # 提取指令内容
    command_text = message_content
    if data.get("message_type") == "group" and is_at_bot:
        # 如果是@机器人，提取去除@部分的文本
        for msg_item in data.get("message", []):
            if msg_item.get("type") == "text":
                text = msg_item.get("data", {}).get("text", "").strip()
                if text:
                    command_text = text
                    break
    
    command_text = command_text.strip()
    if not command_text:
        return False
    
    # 解析指令
    command_parts = command_text.split()
    if not command_parts:
        return False
        
    command = command_parts[0].lower()
    # 处理指令前缀
    if command.startswith("/"):
        command = command[1:]  # 去掉前缀 "/"
        
    args = command_parts[1:] if len(command_parts) > 1 else []
    
    # 处理具体指令
    group_id = data.get("group_id")
    user_id = sender_id
    
    # 帮助指令（所有用户可用）
    if command == "help":
        help_text = "可用指令：\n"
        help_text += "/help - 显示此帮助信息\n"
        help_text += "/limit - 显示当前权限等级\n"
        help_text += "/plugin - 显示插件列表\n"
        help_text += "/persona - 显示当前人格\n"
        help_text += "/persona ls - 列出所有人格\n"
        help_text += "/persona <序号/名称> - 切换人格\n"
        
        if is_authorized(user_id, 3, config_data):  # 主人权限
            help_text += "/reset - 重载插件、自动回复、戳一戳等配置\n"
            help_text += "/op <QQ号> - 添加管理员\n"
            help_text += "/reop <QQ号> - 移除管理员\n"
        elif is_authorized(user_id, 2, config_data):  # 管理员权限
            help_text += "/reset - 重载插件、自动回复、戳一戳等配置\n"
        
        await send_message(websocket, help_text, group_id=group_id, user_id=user_id if not group_id else None)
        return True
    
    # 插件列表指令（所有用户可用）
    elif command == "plugin":
        if loaded_plugins:
            plugin_list_msg = "插件列表：\n"
            for i, plugin_info in enumerate(loaded_plugins, 1):
                plugin_name = plugin_info.get('name', '未知插件')
                plugin_desc = "无描述"
                plugin_cmd = plugin_info.get('cmd', '无触发指令')
                
                # 尝试获取插件描述
                try:
                    plugin_module = plugin_info.get('module')
                    if plugin_module and hasattr(plugin_module, '__doc__'):
                        plugin_desc = plugin_module.__doc__ or '无描述'
                except:
                    pass
                
                plugin_list_msg += f"{i}. {plugin_name} - {plugin_cmd} - {plugin_desc}\n"
            
            plugin_list_msg += "\n使用方法：\n"
            plugin_list_msg += "请查看各插件的使用说明，插件触发方式由插件定义"
        else:
            plugin_list_msg = "当前没有加载任何插件。"
        
        await send_message(websocket, plugin_list_msg, group_id=group_id, user_id=user_id if not group_id else None)
        return True
    
    # 权限指令（所有用户可用）
    elif command == "limit":
        level = get_user_permission_level(user_id, config_data)
        level_names = {3: "主人", 2: "管理员", 1: "用户"}
        perm_text = f"您的权限等级：{level_names.get(level, '未知')} ({level})"
        await send_message(websocket, perm_text, group_id=group_id, user_id=user_id if not group_id else None)
        return True
    
    # 重载配置指令（主人和管理员可用）
    elif command == "reset":
        if not is_authorized(user_id, 2, config_data):
            await send_message(websocket, "权限不足", group_id=group_id, user_id=user_id if not group_id else None)
            return True
            
        # 重载插件
        load_plugins()
        # 重载自动回复规则
        load_auto_reply_rules()
        # 重载随机回复
        load_random_replies()
        
        await send_message(websocket, "LinDream[灵梦]重载插件、自动回复、戳一戳等配置完成", group_id=group_id, user_id=user_id if not group_id else None)
        log_platform_info(f"用户 {user_id} 执行了重载配置指令")
        return True
    
    # 添加管理员（仅主人可用）
    elif command == "op":
        if not is_authorized(user_id, 3, config_data):
            await send_message(websocket, "权限不足", group_id=group_id, user_id=user_id if not group_id else None)
            return True
            
        if not args:
            await send_message(websocket, "请提供要添加的管理员QQ号", group_id=group_id, user_id=user_id if not group_id else None)
            return True
            
        new_admin = args[0]
        if not new_admin.isdigit():
            await send_message(websocket, "QQ号格式错误", group_id=group_id, user_id=user_id if not group_id else None)
            return True
            
        # 更新配置文件
        config_file = "config.json"
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                
            if new_admin not in config.get("admins", []):
                config.setdefault("admins", []).append(new_admin)
                with open(config_file, "w", encoding="utf-8") as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                await send_message(websocket, f"已添加管理员：{new_admin}", group_id=group_id, user_id=user_id if not group_id else None)
                log_platform_info(f"用户 {user_id} 添加了管理员 {new_admin}")
            else:
                await send_message(websocket, f"{new_admin} 已经是管理员", group_id=group_id, user_id=user_id if not group_id else None)
        except Exception as e:
            await send_message(websocket, "添加管理员失败", group_id=group_id, user_id=user_id if not group_id else None)
            log_platform_info(f"添加管理员失败: {e}")
            
        return True
    
    # 移除管理员（仅主人可用）
    elif command == "reop":
        if not is_authorized(user_id, 3, config_data):
            await send_message(websocket, "权限不足", group_id=group_id, user_id=user_id if not group_id else None)
            return True
            
        if not args:
            await send_message(websocket, "请提供要移除的管理员QQ号", group_id=group_id, user_id=user_id if not group_id else None)
            return True
            
        remove_admin = args[0]
        if not remove_admin.isdigit():
            await send_message(websocket, "QQ号格式错误", group_id=group_id, user_id=user_id if not group_id else None)
            return True
            
        # 更新配置文件
        config_file = "config.json"
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                
            if remove_admin in config.get("admins", []):
                config.setdefault("admins", []).remove(remove_admin)
                with open(config_file, "w", encoding="utf-8") as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                await send_message(websocket, f"已移除管理员：{remove_admin}", group_id=group_id, user_id=user_id if not group_id else None)
                log_platform_info(f"用户 {user_id} 移除了管理员 {remove_admin}")
            else:
                await send_message(websocket, f"{remove_admin} 不是管理员", group_id=group_id, user_id=user_id if not group_id else None)
        except Exception as e:
            await send_message(websocket, "移除管理员失败", group_id=group_id, user_id=user_id if not group_id else None)
            log_platform_info(f"移除管理员失败: {e}")
            
        return True
    
    # 指令列表（所有用户可用）
    elif command == "cmd":
        cmd_text = "指令列表：\n"
        cmd_text += "/help - 帮助信息\n"
        cmd_text += "/limit - 权限等级\n"
        cmd_text += "/plugin - 插件列表\n"
        cmd_text += "/persona - 列出人格\n"
        cmd_text += "/persona <序号/名称> - 切换人格\n"
        
        if is_authorized(user_id, 2, config_data):  # 管理员及以上权限
            cmd_text += "/reset - 重载插件、自动回复、戳一戳等配置\n"
        
        if is_authorized(user_id, 3, config_data):  # 主人权限
            cmd_text += "/op <QQ号> - 添加管理员\n"
            cmd_text += "/reop <QQ号> - 移除管理员\n"
        
        await send_message(websocket, cmd_text, group_id=group_id, user_id=user_id if not group_id else None)
        return True
    
    # 人格切换指令（所有用户可用）
    elif command == "persona" or command == "personality":
        personas = list_personas()
        if not personas:
            await send_message(websocket, "没有可用的人格文件", group_id=group_id, user_id=user_id if not group_id else None)
            return True
        
        # 获取命令后的参数
        command_parts = command_text.split()
        args = command_parts[1:] if len(command_parts) > 1 else []
        
        if not args:
            # 如果没有参数，列出人格
            available = "\n".join([f"{i+1}. {persona}" for i, persona in enumerate(personas)])
            response = f"可用人格:\n{available}\n当前人格: {get_user_session(user_id).get('persona', 'default')}\n使用 /persona <序号/名称> 切换人格"
            await send_message(websocket, response, group_id=group_id, user_id=user_id if not group_id else None)
            return True
        elif len(args) == 1 and args[0] == "ls":
            # 列出人格（与不加参数相同）
            available = "\n".join([f"{i+1}. {persona}" for i, persona in enumerate(personas)])
            response = f"可用人格:\n{available}\n当前人格: {get_user_session(user_id).get('persona', 'default')}\n使用 /persona <序号/名称> 切换人格"
            await send_message(websocket, response, group_id=group_id, user_id=user_id if not group_id else None)
            return True
        elif len(args) == 1:
            # 尝试按序号或名称切换人格
            arg = args[0]
            user_session = get_user_session(user_id)
            
            # 检查是否为数字序号
            if arg.isdigit():
                index = int(arg) - 1
                if 0 <= index < len(personas):
                    selected_persona = personas[index]
                    user_session["persona"] = selected_persona
                    await send_message(websocket, f"已切换到人格: {selected_persona}", group_id=group_id, user_id=user_id if not group_id else None)
                    log_platform_info(f"用户 {user_id} 切换到人格: {selected_persona}")
                else:
                    response = f"序号超出范围。使用 /persona 查看可用序号。"
                    await send_message(websocket, response, group_id=group_id, user_id=user_id if not group_id else None)
            else:
                # 按名称切换
                if arg in personas:
                    user_session["persona"] = arg
                    await send_message(websocket, f"已切换到人格: {arg}", group_id=group_id, user_id=user_id if not group_id else None)
                    log_platform_info(f"用户 {user_id} 切换到人格: {arg}")
                else:
                    available = ", ".join(personas)
                    response = f"人格不存在。可用人格: {available}\n使用 /persona 查看带序号的列表"
                    await send_message(websocket, response, group_id=group_id, user_id=user_id if not group_id else None)
            return True
        else:
            await send_message(websocket, "参数错误。使用 /persona 查看帮助", group_id=group_id, user_id=user_id if not group_id else None)
            return True
    
    # 指令列表（所有用户可用）
    elif command == "cmd":
        cmd_text = "指令列表：\n"
        cmd_text += "/help - 帮助信息\n"
        cmd_text += "/limit - 权限等级\n"
        cmd_text += "/plugin - 插件列表\n"
        cmd_text += "/plugin 序号 [命令] - 调用插件\n"
        cmd_text += "/persona - 列出人格\n"
        cmd_text += "/persona <序号/名称> - 切换人格\n"
        
        if is_authorized(user_id, 2, config_data):  # 管理员及以上权限
            cmd_text += "/reset - 重载插件、自动回复、戳一戳等配置\n"
        
        if is_authorized(user_id, 3, config_data):  # 主人权限
            cmd_text += "/op <QQ号> - 添加管理员\n"
            cmd_text += "/reop <QQ号> - 移除管理员\n"
        
        await send_message(websocket, cmd_text, group_id=group_id, user_id=user_id if not group_id else None)
        return True
    
    # 插件列表指令（所有用户可用）
    elif command == "plugin":
        # 如果有参数，尝试调用插件
        if args:
            try:
                # 尝试将第一个参数解析为序号
                plugin_index = int(args[0]) - 1
                if 0 <= plugin_index < len(loaded_plugins):
                    plugin_info = loaded_plugins[plugin_index]
                    plugin_module = plugin_info['module']
                    
                    # 获取命令参数（如果有）
                    plugin_command = " ".join(args[1:]) if len(args) > 1 else ""
                    
                    # 调用插件的命令处理函数（如果存在）
                    if hasattr(plugin_module, 'on_command'):
                        result = plugin_module.on_command(websocket, data, plugin_command, BOT_ID)
                        if result:
                            return True
                    
                    # 如果插件有on_message函数，也可以尝试调用
                    if hasattr(plugin_module, 'on_message'):
                        result = plugin_module.on_message(websocket, data, BOT_ID)
                        if result:
                            return True
                    
                    await send_message(websocket, f"已调用插件: {plugin_info['name']}", group_id=group_id, user_id=user_id if not group_id else None)
                    return True
                else:
                    await send_message(websocket, "插件序号超出范围", group_id=group_id, user_id=user_id if not group_id else None)
                    return True
            except ValueError:
                # 不是数字，可能是插件名
                plugin_name = args[0]
                for plugin_info in loaded_plugins:
                    if plugin_info['name'] == plugin_name:
                        plugin_module = plugin_info['module']
                        plugin_command = " ".join(args[1:]) if len(args) > 1 else ""
                        
                        if hasattr(plugin_module, 'on_command'):
                            result = plugin_module.on_command(websocket, data, plugin_command, BOT_ID)
                            if result:
                                return True
                        
                        if hasattr(plugin_module, 'on_message'):
                            result = plugin_module.on_message(websocket, data, BOT_ID)
                            if result:
                                return True
                        
                        await send_message(websocket, f"已调用插件: {plugin_name}", group_id=group_id, user_id=user_id if not group_id else None)
                        return True
                
                await send_message(websocket, f"未找到插件: {plugin_name}", group_id=group_id, user_id=user_id if not group_id else None)
                return True
        
        # 列出所有已加载的插件
        plugin_list = "插件列表：\n"
        if loaded_plugins:
            for i, plugin_info in enumerate(loaded_plugins, 1):
                plugin_name = plugin_info.get('name', '未知插件')
                # 尝试获取插件描述
                plugin_desc = "无描述"
                try:
                    plugin_module = plugin_info.get('module')
                    if plugin_module and hasattr(plugin_module, 'PLUGIN_CONFIG'):
                        plugin_desc = plugin_module.PLUGIN_CONFIG.get('description', '无描述')
                    elif plugin_module and hasattr(plugin_module, '__doc__'):
                        plugin_desc = plugin_module.__doc__ or '无描述'
                except:
                    pass
                plugin_list += f"{i}. {plugin_name} - {plugin_desc}\n"
            
            plugin_list += "\n使用方法：\n"
            plugin_list += "/plugin 序号 [命令] - 按序号调用插件\n"
            plugin_list += "/plugin 插件名 [命令] - 按名称调用插件\n"
            plugin_list += "例如：/plugin 1 或 /plugin example"
        else:
            plugin_list += "当前没有可用的插件。"
        
        await send_message(websocket, plugin_list, group_id=group_id, user_id=user_id if not group_id else None)
        return True
    
    # 未知指令
    else:
        await send_message(websocket, "未知指令，发送 /help 查看可用指令", group_id=group_id, user_id=user_id if not group_id else None)
        return True

# =========================
# 配置加载
# =========================
def load_config():
    global BOT_ID, MAX_DOWNLOAD_WORKERS
    config_file = "config.json"
    
    if not os.path.exists(config_file):
        print(Fore.LIGHTYELLOW_EX + "首次启动，正在配置机器人...")
        
        # 询问机器人主人QQ号
        owner_id = input("请输入机器人主人QQ号: ").strip()
        while not owner_id or not owner_id.isdigit():
            owner_id = input("输入无效，请输入机器人主人QQ号: ").strip()
        
        BOT_ID = input("请输入机器人QQ号: ").strip()
        while not BOT_ID or not BOT_ID.isdigit():
            BOT_ID = input("输入无效，请输入机器人QQ号: ").strip()
        
        # 询问AI API配置
        use_ai = input("是否启用AI聊天功能？(y/n，默认n): ").strip().lower()
        api_key = ""
        api_url = "https://apis.iflow.cn/v1/chat/completions"
        model_name = "qwen3-coder-plus"
        
        if use_ai == 'y':
            api_key = input("请输入AI API Key: ").strip()
            custom_url = input("请输入AI API地址 (默认https://apis.iflow.cn/v1/chat/completions，回车使用默认): ").strip()
            if custom_url:
                api_url = custom_url
                
            custom_model = input("请输入模型名称 (默认qwen3-coder-plus，回车使用默认): ").strip()
            if custom_model:
                model_name = custom_model
        
        max_workers_input = input("请输入下载线程最大并发数 (默认3): ").strip()
        try:
            MAX_DOWNLOAD_WORKERS = int(max_workers_input) if max_workers_input else 3
        except ValueError:
            MAX_DOWNLOAD_WORKERS = 3
            
        config_data = {
            "bot_id": BOT_ID,
            "owner_id": owner_id,  # 添加主人QQ号
            "api_key": api_key,    # AI API Key
            "api_url": api_url,    # AI API地址
            "model_name": model_name,  # 模型名称
            "max_download_workers": MAX_DOWNLOAD_WORKERS,
            "admins": [],  # 管理员列表
            "users": []   # 用户列表
        }
        
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        print(Fore.LIGHTGREEN_EX + f"配置已保存到 {config_file}")
    else:
        with open(config_file, "r", encoding="utf-8") as f:
            config_data = json.load(f)
            BOT_ID = config_data.get("bot_id")
            MAX_DOWNLOAD_WORKERS = config_data.get("max_download_workers", 3)
    
    # 加载自动回复规则和随机回复
    load_auto_reply_rules()
    load_random_replies()
    
    # 系统报错提示
    print(Fore.LIGHTRED_EX + "注意：如遇问题请及时检查配置文件")

# =========================
# WebSocket 主处理
# =========================
async def server(websocket):
    log_platform_info(f"NapCat 已连接: {websocket.remote_address}")

    try:
        async for raw in websocket:
            try:
                data = json.loads(raw)
            except:
                log_platform_info("收到无法解析的原始消息: " + raw)
                continue

            # 好友列表
            if data.get("echo")=="friends" and data.get("status")=="ok":
                log_platform_info("好友列表：")
                for f in data.get("data", []):
                    nickname = f.get('nickname')
                    uid = f.get('user_id')
                    msg = f" - {nickname} ({uid})"
                    print(Fore.LIGHTCYAN_EX + msg)
                    write_log(msg)
                continue

            # 群列表
            if data.get("echo")=="groups" and data.get("status")=="ok":
                log_platform_info("群聊列表：")
                for g in data.get("data", []):
                    gname = g.get('group_name')
                    gid = g.get('group_id')
                    msg = f" - {gname} ({gid})"
                    print(Fore.LIGHTMAGENTA_EX + msg)
                    write_log(msg)
                continue

            post_type = data.get("post_type")

            # 消息
            if post_type=="message":
                # 检测是否为机器人自身发送的消息（通过QQ号判断）
                sender = data.get("sender", {})
                sender_id = sender.get("user_id")
                
                # 如果是机器人发送的消息，添加标记
                if str(sender_id) == str(BOT_ID):
                    # 机器人自身发送的消息
                    is_bot_message = True
                else:
                    is_bot_message = False
                
                msg_id = data.get("message_id") or data.get("msg_id")
                message_cache[msg_id] = data
                media_files = await handle_media(
                    data.get("message", []),
                    group_name=data.get("group_name","") if data.get("message_type")=="group" else "",
                    group_id=data.get("group_id","") if data.get("message_type")=="group" else "",
                    sender_name=sender.get("nickname","未知"),
                    sender_id=sender.get("user_id","未知")
                )
                log_communication(data, media_files, is_bot_message)
                
                # 处理自动回复
                await handle_auto_reply(websocket, data)
                continue

            # 系统事件
            if post_type=="meta_event":
                log_system_event(data)
                continue

            # 戳一戳事件
            if post_type=="notice" and data.get("notice_type")=="notify" and data.get("sub_type")=="poke":
                group_id = data.get("group_id")
                user_id = data.get("user_id")
                target_id = data.get("target_id")
                
                # 获取群名和用户名
                group_name = "私聊"
                if group_id:
                    # 尝试从缓存中获取群名
                    group_name = f"群:{group_id}"
                
                # 尝试从缓存中获取用户名
                user_name = f"用户:{user_id}"
                target_name = f"用户:{target_id}"
                
                msg = f"[戳一戳] {group_name} | {user_name} 戳了 {target_name}"
                print(Fore.LIGHTBLUE_EX + msg)
                write_log(msg)
                
                # 如果是戳机器人，随机回复
                if str(target_id) == str(BOT_ID) and random_replies:
                    reply = random.choice(random_replies)
                    if group_id:
                        await send_message(websocket, reply, group_id=group_id)
                    else:
                        await send_message(websocket, reply, user_id=user_id)
                    log_platform_info(f"触发戳一戳随机回复: {reply}")
                
                continue

            # 群名片变更事件
            if post_type=="notice" and data.get("notice_type")=="group_card":
                group_id = data.get("group_id")
                user_id = data.get("user_id")
                card_new = data.get("card_new", "")
                card_old = data.get("card_old", "")
                
                # 获取群名和用户名
                group_name = f"群:{group_id}"
                user_name = f"用户:{user_id}"
                
                msg = f"[群名片变更] {group_name} | {user_name} | 旧名片: '{card_old}' -> 新名片: '{card_new}'"
                print(Fore.LIGHTBLUE_EX + msg)
                write_log(msg)
                continue

            # 撤回
            if post_type=="notice" and data.get("notice_type")=="group_recall":
                log_recall(data)
                continue

            # 输入状态事件
            if post_type=="notice" and data.get("notice_type")=="notify" and data.get("sub_type")=="input_status":
                user_id = data.get("user_id")
                group_id = data.get("group_id")
                status_text = data.get("status_text", "")
                event_type = data.get("event_type")
                
                # 获取群名和用户名
                group_name = "私聊"
                if group_id and group_id != 0:
                    group_name = f"群:{group_id}"
                
                user_name = f"用户:{user_id}"
                
                msg = f"[输入状态] {group_name} | {user_name} | 状态: {status_text} | 类型: {event_type}"
                print(Fore.LIGHTBLUE_EX + msg)
                write_log(msg)
                continue

            # 群成员增加事件
            if post_type=="notice" and data.get("notice_type")=="group_increase":
                group_id = data.get("group_id")
                user_id = data.get("user_id")
                operator_id = data.get("operator_id")
                sub_type = data.get("sub_type")
                
                # 获取群名和用户名
                group_name = f"群:{group_id}"
                user_name = f"用户:{user_id}"
                operator_name = f"操作者:{operator_id}"
                
                msg = f"[群成员增加] {group_name} | {user_name} | {operator_name} | 方式: {sub_type}"
                print(Fore.LIGHTBLUE_EX + msg)
                write_log(msg)
                continue

            # 群成员减少事件
            if post_type=="notice" and data.get("notice_type")=="group_decrease":
                group_id = data.get("group_id")
                user_id = data.get("user_id")
                operator_id = data.get("operator_id")
                sub_type = data.get("sub_type")
                
                # 获取群名和用户名
                group_name = f"群:{group_id}"
                user_name = f"用户:{user_id}"
                operator_name = f"操作者:{operator_id}"
                
                # 解释子类型
                sub_type_desc = {
                    "leave": "主动退群",
                    "kick": "被踢出群",
                    "kick_me": "机器人被踢出群"
                }
                
                sub_type_text = sub_type_desc.get(sub_type, sub_type)
                
                msg = f"[群成员减少] {group_name} | {user_name} | {operator_name} | 方式: {sub_type_text}"
                print(Fore.LIGHTBLUE_EX + msg)
                write_log(msg)
                continue

            # 群文件上传事件
            if post_type=="notice" and data.get("notice_type")=="group_upload":
                group_id = data.get("group_id")
                user_id = data.get("user_id")
                file_info = data.get("file", {})
                
                # 获取文件信息
                file_name = file_info.get("name", "未知文件")
                file_size = file_info.get("size", 0)
                file_id = file_info.get("id", "")
                
                # 格式化文件大小
                def format_size(size):
                    for unit in ['B', 'KB', 'MB', 'GB']:
                        if size < 1024:
                            return f"{size:.1f}{unit}"
                        size /= 1024
                    return f"{size:.1f}TB"
                
                formatted_size = format_size(file_size) if file_size > 0 else "未知大小"
                
                # 获取群名和用户名
                group_name = f"群:{group_id}"
                user_name = f"用户:{user_id}"
                
                # 显示文件信息和下载链接
                msg = f"[文件上传] {group_name} | {user_name} | 文件: {file_name} | 大小: {formatted_size}"
                print(Fore.LIGHTBLUE_EX + msg)
                write_log(msg)
                
                # 显示下载链接信息
                if file_id:
                    download_msg = f"文件下载链接: 群{group_id}文件ID {file_id}"
                    log_platform_info(download_msg)
                continue

            # 检查是否有echo字段（可能是消息发送响应）
            if "echo" in data:
                # 这可能是消息发送响应，简单记录
                if data.get("status") == "ok":
                    log_platform_info("消息发送成功")
                else:
                    log_platform_info(f"消息发送失败: {data.get('message', '')}")
                continue

            log_platform_info("未知事件: " + str(data))
    except websockets.exceptions.ConnectionClosed:
        log_platform_info("NapCat 断开连接")
    except Exception as e:
        log_platform_info(f"错误: {e}")

# =========================
# 主程序
# =========================
async def main():
    load_config()
    
    # 加载插件
    load_plugins()
    
    # 启动下载队列workers
    for i in range(MAX_DOWNLOAD_WORKERS):
        asyncio.create_task(download_worker())
    
    log_platform_info(f"Python WS 服务器启动：ws://0.0.0.0:2048")
    log_platform_info(f"机器人QQ: {BOT_ID}")
    log_platform_info(f"下载线程数: {MAX_DOWNLOAD_WORKERS}")
    log_platform_info(f"已加载 {len(loaded_plugins)} 个插件")
    
    async with websockets.serve(server, "0.0.0.0", 2048) as ws_server:
        try:
            await asyncio.Future()  # 永不退出
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            log_platform_info("服务器手动终止")
            for task in video_cleanup_tasks:
                task.cancel()

if __name__=="__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log_platform_info("程序已退出")
# 项目文本化总览

## 项目结构树

```
├── .gitignore
├── AGENTS.md
├── README.md
├── docker-compose.yml
├── generate_project_text.py
├── project_text.md
├── start.ps1
├── stop.ps1
├── test.html
├── gateway/
│   ├── Dockerfile
│   ├── config.py
│   ├── dto.py
│   ├── main.py
│   ├── requirements.txt
│   ├── utils.py
│   └── worker_manager.py
├── worker/
│   ├── Dockerfile
│   ├── dto.py
│   ├── kernel_manager.py
│   ├── main.py
│   ├── requirements.txt
│   ├── assets/
│   │   └── simhei.ttf
│   ├── supervisor/
│   │   └── supervisord.conf
```

## 文件内容

--- 

`AGENTS.md`

```markdown
# 代码规范 aka agents.md

## 基础格式规范
- 所有的代码文件必须使用UTF-8编码
- 所有的代码文件必须使用4个空格缩进，不允许使用Tab缩进
- PR/commit时不要有任何语法错误（红线）
- 文件末尾必须有一个换行符
- 使用PyCharm默认的代码规范（变量命名，类命名，换行，空格，注释）（在默认情况下不要出现黄线，明显是linter的错误的除外）

## 类型注解规范
- 所有的类型注解都必须使用Python 3.10+的简化语法
    - 例如：使用 `dict[str, Any] | None` 而不是 `Optional[Dict[str, Any]]`
    - **唯一例外**：用字符串表示可空的类型标注时，不能用 `"TypeName" | None`（这是语法错误），必须使用 `Optional['TypeName']`
- 参数、类变量、实例变量等必须有类型注解，函数返回必须要注明类型
- 所有的类型注解都必须是明确的类型，不能使用 `Any` 或 `object`，除非确实无法确定类型，  
  需要明确使用todo标注，以便后期研究类型
- 所有的类型注解都必须是具体的类型，不能使用泛型（如 `List`、`Dict`、`Tuple`、`Set`、`Union` 等）  
  必须使用具体的类型（如 `list[int]`、`dict[str, Any]`、`tuple[int, str]`、`set[str]`、`int | str` 等）
- 所有的类型注解都必须是导入的类型，不能使用字符串表示类型（如 `def func(param: 'CustomType') -> 'ReturnType':`）  
  除非是**前向引用**（即类型在当前作用域中还未定义）

## 异步编程规范
- 使用FastAPI管理的事件循环，不要再新建任何事件循环，不论是在任何线程或任何子进程中
- IO操作必须使用协程，不涉及任何CPU密集或IO的操作必须不使用协程，按需使用to_thread线程或Celery Worker
- 所有的数据库操作必须使用异步数据库驱动（如SQLModel的AsyncSession），不允许使用同步数据库驱动
- 所有的HTTP请求必须使用异步HTTP客户端（如aiohttp），不允许使用同步HTTP客户端
- 所有的文件操作必须使用异步文件操作库（如aiofiles），不允许使用同步文件操作
- 所有的子进程操作必须使用异步子进程库（如anyio），不允许使用同步子进程库
- 所有的第三方库调用必须使用异步版本，不允许使用同步版本，如果没有同步版本，视cpu负载情况使用to_thread线程或Celery Worker
- 所有的高cpu阻塞操作必须使用to_thread线程或Celery Worker，不允许在协程中直接调用高cpu阻塞操作

## 函数与参数规范
- 一个方法最多五个参数，多了考虑拆分方法或合并参数（SQLModel），不要简单的用tuple或dict

## 代码格式规范
- **容器类型定义**：元组、字典、列表定义时，若定义只用了一行，则最后一个元素后面一律不加逗号，否则一律加逗号
- **括号换行**：括号要么不换行，要么换行且用下面的形式写（一行最多一个变量，以逗号和换行分割）

### 示例代码
```python
from loguru import logger as l

from api_client_models import (
    AgentModelsRequest,
    ReportRequest,
    SaveMemoryRequest,
    UserInfoResponse,
)

async def lookup_user_info(
        session: AsyncSession,
        user_id: int,
        short_name: str,
        data_1_with_a_long_name: dict[str, Any] | None,
        data_2_with_a_even_longer_name: CustomType
) -> UserInfoResponse:
    user = await User.get(session, User.id == user_id)
    new_dict = { user_id, short_name }
    l.debug(f"查到的数据: {new_dict}")
    result = UserInfoResponse(
        user.id,
        user.a_long_attribute,
        data_1_with_a_long_name,
        data_2_with_a_even_longer_name,
    )

    return result
```

## 文档与注释规范
- 复杂的类或函数（无法从名字推断明确的操作，如 `handle_connection()`）一律要写docstring，采用reStructuredText风格

## 字符串处理规范
- **引号使用**：单引号 `'` 用于给电脑看的文本（字典的键），双引号 `"` 用于给人看的文本（面向用户的提示，面向开发者的注释、log信息等）
- **字符串格式化**：所有的字符串都用f-string格式化，不要使用 `%` 或 `.format()`
- **多行字符串**：多行字符串使用"""或'''，"""给人看(如docstring)，'''给电脑看（如SQL语句或HTML内容）

## 命名规范
- 除非专有名词，代码中不要出现任何拼音变量名，所有变量名必须是英文
- 所有的变量名、函数名、方法名、参数名都必须使用蛇形命名法（snake_case）
- 所有的类名都必须使用帕斯卡命名法（PascalCase）
- 所有的常量名都必须使用全大写蛇形命名法（UPPER_SNAKE_CASE）
- 所有的私有变量、私有方法都必须使用单下划线前缀（_private_var）
- 所有的非常私有变量、非常私有方法都必须使用双下划线前缀（__very_private_var）
- 所有的布尔变量都必须使用is_、has_、can_、should_等前缀命名，且变量名必须是形容词或动词短语（如 is_valid, has_data, can_execute, should_retry）

## 异常处理规范
- 所有的异常都必须被捕获，且要有明确的处理逻辑
- 如果出现错误，不要return None，这样会造成隐藏的不易发现的错误，必须明确抛出异常

## 日志处理规范
- 所有的日志都必须用 `from loguru import logger as l` 处理，不要使用print
- 所有的日志都必须有明确的上下文，且要有明确的日志级别

## 框架的使用
- 使用SQLModel，而不是Pydantic或SQLAlchemy。使用SQLModel时禁止从future导入annotations
- 使用FastAPI，而不是Flask或Django
- 使用Aiohttp，而不是Requests
- 使用Aiofiles，而不是内置的open
```python
import os as sync_os
from aiofiles import os, open
...
async with open('file.txt', 'r') as f:
    content = await f.read()
...
path = sync_os.path(...)
```
- 使用Anyio，而不是内置的subprocess
- 使用Loguru，而不是内置的logging
  `from loguru import logger as l`
- 使用Celery，而不是内置的multiprocessing
- 使用GitHub Desktop，而不是直接在文件系统操作
- 使用PyCharm，而不是其他IDE

## AI编码
- 如果有条件，inline completion插件使用GitHub Copilot，而不是JetBrains自带的
- 如果让AI直接编码，使用Gemini 2.5 Pro及以上, Claude 3.7 Sonnet Thinking及以上，而不是GPT系列模型，DeepSeek，豆包，文心一言等
- 使用AI生成代码时，提示词必须带上这个代码规范
- 在实现任何功能前，必须先看看有没有现成的解决方案，比如pypi包，不要重复造轮子

# SQLModel规范
- 使用字段后面的"""..."""（docstring）而不是参数description="..."来写字段描述
  例如：
```python
class User(SQLModel, table=True):
    model_config = ConfigDict(use_attribute_docstrings=True)

    id: int = Field(default=None, primary_key=True, description="用户ID")  # 错误示范
    name: str = Field(description="用户名")  # 错误示范
    email: str = Field(unique=True)  # 正确示范
    """用户邮箱"""
```

  
---

**注意**：此规范会持续更新，对此文件有任何建议修改可以发起PR，没有在规范里提到的都没有硬性要求，可以参考[PEP 8](https://peps.python.org/pep-0008/)

```

--- 

`README.md`

```markdown
# Code Interpreter - 高性能、可伸缩、高安全性的 Python 代码沙箱

本项目是一个通过 API 驱动的 Python 代码执行沙箱。它采用中心化的 **API 网关 (Gateway)** 和动态的 **工作实例池 (Worker Pool)** 架构，为每个用户提供完全隔离的、有状态的 Python 执行会话。

每个工作实例都在一个独立的、受资源和网络限制的 Docker 容器中运行，并通过内部的 Jupyter Kernel 保持代码执行的上下文状态，提供了极致的安全性、会话连续性和高性能。

## 核心特性

-   **有状态会话**: 每个用户 (通过 `user_uuid` 标识) 在会话期间会被唯一地映射到一个工作实例，从而保证了变量、函数定义和导入的包在连续的 API 请求之间得以保持。

-   **极致隔离与安全**:
    -   **中心化访问控制**: 所有的请求都必须通过 API 网关，网关负责统一的令牌认证，工作实例不直接暴露于外部。
    -   **网络隔离**: 所有工作实例都运行在一个**完全隔离的 Docker 内部网络**中。这意味着工作实例无法访问互联网，也无法被外部网络直接访问，有效防止了数据外泄和恶意代码的网络攻击。
    -   **进程/资源隔离**: 每个工作实例运行在独立的 Docker 容器中，实现了操作系统级别的资源隔离。

-   **高性能与高并发**:
    -   **池化架构**: 系统维护一个预热的空闲工作实例池。当用户首次请求时，网关会立即从池中分配一个实例，实现了近乎零延迟的沙箱环境获取。
    -   **全异步设计**: 网关和工作实例均基于 FastAPI 构建，整个请求处理链路完全异步化，能够轻松处理大量并发请求。

-   **高鲁棒性与自愈能力**:
    -   **健康检查**: 网关在创建并分配工作实例前会对其进行严格的健康检查，确保内部服务完全就绪。
    -   **超时自动重置**: 当代码执行时间超过预设阈值时，工作实例内部的 Jupyter Kernel 会被自动重置，以防死循环或长时间的阻塞操作拖垮环境。
    -   **闲置自动回收**: 网关的后台任务会周期性地检查并回收长时间未活动的实例，自动释放资源，并维持池中最小空闲实例数。
    -   **会话主动释放**: 提供了 `/release` 接口，允许用户主动结束会话并立即销毁其实例，释放资源。

## 架构解析

项目主要由两大部分组成：**API 网关 (Gateway)** 和 **工作实例 (Worker)**。

1.  **API 网关 (Gateway)**
    *   作为系统的唯一入口，负责接收所有外部 API 请求。
    *   **认证中心**: 校验所有请求头中的 `X-Auth-Token`。
    *   **工作池管理器 (`WorkerManager`)**:
        *   维护一个由 `Worker` 容器组成的池，包括一个最小数量的空闲实例。
        *   当接收到新用户的请求时，从池中取出一个空闲实例并与该用户的 `user_uuid` 绑定。
        *   如果池中没有空闲实例且未达到总数上限，则动态创建新的实例。
        *   负责实例的生命周期管理，包括创建、健康检查、闲置回收和销毁。
    *   **请求代理**: 将已认证和分配的请求，透明地代理到对应的内部工作实例上。

2.  **工作实例 (Worker)**
    *   一个标准化的、自包含的 Docker 容器，是实际的代码执行单元。
    -   容器内部由 `Supervisor` 管理两个核心进程：
        *   **Jupyter Kernel**: 提供一个有状态的 Python 运行时环境。这是实现会话连续性的关键。
        *   **FastAPI 服务**: 暴露一个简单的内部 HTTP API (`/execute`, `/reset`, `/health`)，接收来自网关的指令。
    *   **内核管理器 (`JupyterKernelManager`)**:
        *   FastAPI 服务通过该模块与 Jupyter Kernel 进行交互，通过 WebSocket 发送代码并实时捕获输出、图像或错误。

## 快速开始

### 1. 前提条件

-   [Docker](https://www.docker.com/) 和 [Docker Compose](https://docs.docker.com/compose/) 已正确安装并正在运行。
-   一个可以发送 HTTP 请求的客户端 (如 cURL, Postman, 或者 Python 的 `httpx` 库)。

### 2. 启动服务

本项目被设计为使用 Docker Compose 进行一键部署。

1.  **构建并启动服务**
    在项目根目录下，执行以下命令：

    ```bash
    docker-compose up --build -d
    ```

    此命令会：
    -   构建 `gateway` 和 `worker` 的 Docker 镜像。
    -   创建一个名为 `code-interpreter_workers_isolated_net` 的隔离内部网络。
    -   启动网关服务，并将其 `3874` 端口映射到宿主机的 `3874` 端口。
    -   根据网关的配置 (`gateway/config.py`)，自动初始化工作池。

2.  **获取认证令牌**
    服务首次启动时，一个认证令牌会自动在 `gateway/` 目录下生成，文件名为 `auth_token.txt`。你也可以通过设置环境变量 `AUTH_TOKEN` 来自定义令牌。

## API 接口文档

所有 API 请求都应发送到 Gateway 地址 (默认为 `http://127.0.0.1:3874`)。

### 认证

所有接口都需要在 HTTP 请求头中提供认证令牌。
-   **Header**: `X-Auth-Token`
-   **Value**: `你的认证令牌`

---

### 1. 执行代码

在用户的会话中执行一段 Python 代码。

-   **Endpoint**: `POST /execute`
-   **描述**: 为指定的 `user_uuid` 分配一个工作实例（如果尚不存在），然后在该实例中执行代码。后续使用相同 `user_uuid` 的请求将在同一个实例中执行，从而维持状态。
-   **Request Body**:
    ```json
    {
      "user_uuid": "string",
      "code": "string"
    }
    ```
    -   `user_uuid` (string, required): 用户的唯一标识符。建议使用 UUID。
    -   `code` (string, required): 需要执行的 Python 代码字符串。

-   **Success Response (200 OK)**:
    ```json
    {
      "result_text": "string | null",
      "result_base64": "string | null"
    }
    ```
    -   `result_text`: 代码的标准输出 (stdout) 或最后一个表达式的文本表示。
    -   `result_base64`: 如果代码生成了图像 (例如使用 matplotlib)，此字段将包含 PNG 图像的 Base64 编码字符串。

-   **Error Responses**:
    -   `400 Bad Request`: 代码执行出错（例如语法错误）或执行超时。
    -   `401 Unauthorized`: 认证令牌无效或缺失。
    -   `503 Service Unavailable`: 工作池已满，暂时没有可用的工作实例。

---

### 2. 释放会话

主动结束一个用户的会话并销毁其关联的工作实例。

-   **Endpoint**: `POST /release`
-   **描述**: 立即回收指定 `user_uuid` 占用的资源。如果不主动调用，实例也会在闲置超时后被系统自动回收。
-   **Request Body**:
    ```json
    {
      "user_uuid": "string"
    }
    ```
    -   `user_uuid` (string, required): 需要释放的会话的用户标识符。

-   **Success Response (200 OK)**:
    ```json
    {
      "status": "ok",
      "detail": "Worker for user <user_uuid> has been released."
    }
    ```

---

### 3. 获取系统状态 (管理接口)

查询当前工作池的状态。

-   **Endpoint**: `GET /status`
-   **描述**: 返回关于工作实例数量和状态的摘要信息，主要用于监控和调试。
-   **Request Body**: None
-   **Success Response (200 OK)**:
    ```json
    {
        "total_workers": 10,
        "busy_workers": 3,
        "idle_workers_in_pool": 2,
        "is_initializing": false
    }
    ```

## 使用示例 (Python)

下面是一个使用 `httpx` 库与服务交互的完整示例。

```python
import httpx
import asyncio
import uuid
import base64
import os

# --- 配置 ---
GATEWAY_URL = "http://127.0.0.1:3874"
# 从 gateway/auth_token.txt 文件中获取
AUTH_TOKEN = "your-actual-auth-token" 
# 为这个会话生成一个唯一的用户 ID
USER_ID = str(uuid.uuid4())

HEADERS = {"X-Auth-Token": AUTH_TOKEN}

async def execute_code(client: httpx.AsyncClient, session_id: str, code: str):
    """一个辅助函数，用于发送执行请求并打印结果。"""
    print(f"\n--- 正在执行代码 ---\n{code.strip()}")
    payload = {"user_uuid": session_id, "code": code}
    
    try:
        response = await client.post(f"{GATEWAY_URL}/execute", json=payload, headers=HEADERS)
        response.raise_for_status() # 如果状态码不是 2xx，则抛出异常
        
        data = response.json()
        if data.get("result_text"):
            print(">>> 文本结果:\n" + data["result_text"])
        if data.get("result_base64"):
            print(">>> 成功生成图像！(返回 base64 编码的 PNG 数据)")
            # 可选：将图像数据保存到文件
            img_data = base64.b64decode(data["result_base64"])
            output_filename = f"output_{session_id[:8]}.png"
            with open(output_filename, "wb") as f:
                f.write(img_data)
            print(f"    图像已保存为 {output_filename}")
            
    except httpx.HTTPStatusError as e:
        print(f"执行失败: {e.response.status_code} - {e.response.text}")
    except httpx.RequestError as e:
        print(f"请求错误: {e}")


async def release_session(client: httpx.AsyncClient, session_id: str):
    """辅助函数，用于释放会话。"""
    print("\n--- 正在释放工作实例 ---")
    release_payload = {"user_uuid": session_id}
    response = await client.post(f"{GATEWAY_URL}/release", json=release_payload, headers=HEADERS)
    if response.status_code == 200:
        print("成功释放:", response.json().get('detail'))
    else:
        print("释放失败:", response.text)


async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 示例 1: 定义变量
        await execute_code(client, USER_ID, "a = 10\nb = 20")
        
        # 示例 2: 复用上一次执行的变量 'a' 和 'b' (有状态)
        await execute_code(client, USER_ID, "result = a * b\nprint(f'The product is {result}')\nresult")

        # 示例 3: 生成一个图像 (matplotlib)
        matplotlib_code = """
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.figure(figsize=(5, 3))
plt.plot(x, y)
plt.title('Sine Wave')
plt.grid(True)
plt.show()
        """
        await execute_code(client, USER_ID, matplotlib_code)

        # 示例 4: 主动释放会话和资源
        await release_session(client, USER_ID)


if __name__ == "__main__":
    # 替换为你的真实令牌
    if AUTH_TOKEN == "your-actual-auth-token":
        # 尝试从文件中读取令牌
        try:
            with open(os.path.join("gateway", "auth_token.txt"), "r") as f:
                AUTH_TOKEN = f.read().strip()
                HEADERS["X-Auth-Token"] = AUTH_TOKEN
        except FileNotFoundError:
             print("错误: 请将 AUTH_TOKEN 变量替换为你的真实令牌，或确保 gateway/auth_token.txt 文件存在。")
             exit(1)
             
    asyncio.run(main())
```

## Roadmap

-   [ ] 增加文件上传下载功能
-   [ ] 增加 `site-packages` 的持久化存储
-   [ ] 更精细化的资源限制 (CPU, 内存)
-   [ ] 支持自定义 Python 环境和预装库

```

--- 

`docker-compose.yml`

```
# docker-compose.yml

version: '3.8'

services:
  gateway:
    build:
      context: ./gateway
      dockerfile: Dockerfile
    image: code-interpreter-gateway:latest
    container_name: code-interpreter_gateway
    restart: unless-stopped
    ports:
      # 映射 Gateway 对外端口，根据您的 Dockerfile，这里是 3874
      - "3874:3874"
    volumes:
      # 将宿主机的 Docker socket 挂载到容器内，以便 Gateway 可以管理其他容器
      - /var/run/docker.sock:/var/run/docker.sock
      # 挂载一个卷用于持久化 auth_token
      - gateway_data:/gateway
    networks:
      # [新增] 连接到外部网络（默认桥接），以便 Gateway 自身可以访问互联网
      - code-interpreter-gateway-external-net
      # [更新] 连接到内部隔离网络，以便 Gateway 可以与 Worker 通信
      - code-interpreter-workers-isolated-net
    environment:
      # 确保 Gateway 知道要将 Worker 连接到哪个内部网络
      - INTERNAL_NETWORK_NAME=code-interpreter_workers_isolated_net
    depends_on:
      - worker # 确保 worker 镜像被构建

  worker:
    build:
      context: ./worker
      dockerfile: Dockerfile
    image: code-interpreter-worker:latest
    container_name: code-interpreter_worker_builder # 给 builder 容器一个固定名字，方便清理
    entrypoint: /bin/true # 覆盖 ENTRYPOINT，使其立即退出
    networks:
      # [更新] 只连接到内部隔离网络。这个 builder 容器本身不应需要互联网
      - code-interpreter-workers-isolated-net

networks:
  # [新增] Gateway 外部网络（标准桥接），允许 Gateway 访问互联网
  code-interpreter-gateway-external-net:
    driver: bridge
    name: code-interpreter_gateway_external_net

  # [新增 & 关键] Worker 内部隔离网络。internal: true 是隔离的关键！
  code-interpreter-workers-isolated-net:
    driver: bridge
    internal: true # <--- 这一行是确保 Worker 无法联网的关键
    name: code-interpreter_workers_isolated_net

volumes:
  gateway_data:

```

--- 

`gateway\Dockerfile`

```
FROM python:3.12-slim-bookworm

LABEL maintainer="Foxerine"
LABEL description="Gateway and manager for the Python code interpreter."

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1

WORKDIR /gateway
COPY ./requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY . /gateway

EXPOSE 3874
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3874"]

```

--- 

`gateway\config.py`

```python
# gateway/config.py

"""
Centralized configuration for the Gateway service.
"""
import os
import uuid
from pathlib import Path

from loguru import logger as l

# --- Authentication ---
# The master token required to use the gateway services.
def get_auth_token():
    token_file = Path("/gateway/auth_token.txt")
    if "AUTH_TOKEN" in os.environ:
        return os.environ["AUTH_TOKEN"]
    elif token_file.exists():
        return token_file.read_text().strip()
    else:
        new_token = str(uuid.uuid4())
        token_file.write_text(new_token)
        return new_token

AUTH_TOKEN: str = get_auth_token()

# --- Worker Management ---
# The name of the Docker Compose service defined for the worker
WORKER_SERVICE_NAME: str = "code-interpreter_worker"

# The name of the internal Docker network workers and the gateway share
# [更新] 更改为新的隔离网络名称
INTERNAL_NETWORK_NAME: str = os.environ.get("INTERNAL_NETWORK_NAME", "code-interpreter_workers_isolated_net")

# The image to use for creating new worker containers.
# This should match the image built for the worker service.
WORKER_IMAGE_NAME: str = "code-interpreter-worker:latest" # Docker compose creates this image name

# --- Pool Sizing ---
# The minimum number of idle workers to keep ready in the pool.
MIN_IDLE_WORKERS: int = 2

# The absolute maximum number of concurrent workers allowed.
MAX_TOTAL_WORKERS: int = 30

# --- Timeout ---
# Time in seconds a worker can be idle (not executing code) before being recycled.
WORKER_IDLE_TIMEOUT: int = 3600  # 1 hour

# How often the background task runs to check for timed-out workers.
RECYCLING_INTERVAL: int = 300  # 5 minutes

```

--- 

`gateway\dto.py`

```python
from enum import StrEnum
from pydantic import BaseModel, Field
import time

class WorkerStatus(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    CREATING = "creating"
    ERROR = "error"

class Worker(BaseModel):
    """Represents the internal state of a Worker container in the Gateway."""
    container_id: str
    container_name: str
    internal_url: str
    status: WorkerStatus = WorkerStatus.CREATING
    user_uuid: str | None = None
    last_active_timestamp: float = Field(default_factory=time.time)

class ExecuteRequest(BaseModel):
    user_uuid: str
    code: str

class ExecuteResponse(BaseModel):
    result_text: str | None = None
    result_base64: str | None = None

class ReleaseRequest(BaseModel):
    user_uuid: str

class ReleaseResponse(BaseModel):
    status: str
    detail: str

class ErrorDetail(BaseModel):
    detail: str

```

--- 

`gateway\main.py`

```python
import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger as l

import config
from dto import (
    ExecuteRequest, ExecuteResponse,
    ReleaseRequest, ReleaseResponse
)
from utils import raise_internal_error
from worker_manager import WorkerManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure and initialize the WorkerManager
    l.info(f"token: {config.AUTH_TOKEN}")

    await WorkerManager.init(
        worker_image_name=config.WORKER_IMAGE_NAME,
        internal_network_name=config.INTERNAL_NETWORK_NAME,
        min_idle_workers=config.MIN_IDLE_WORKERS,
        max_total_workers=config.MAX_TOTAL_WORKERS,
        worker_idle_timeout=config.WORKER_IDLE_TIMEOUT,
        recycling_interval=config.RECYCLING_INTERVAL,
    )

    # Start the background task
    recycling_task = asyncio.create_task(WorkerManager.recycle_timed_out_workers())
    yield
    # Cleanup on shutdown
    recycling_task.cancel()
    l.info("Shutting down. Cleaning up all worker containers...")
    await WorkerManager.close()


app = FastAPI(title="Code Interpreter Gateway", lifespan=lifespan)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法 (GET, POST, OPTIONS 等)
    allow_headers=["*"],  # 允许所有请求头 (包括 X-Auth-Token)
)

@app.exception_handler(Exception)
async def handle_unexpected_exceptions(request: Request, exc: Exception):
    """
    捕获所有未经处理的异常，防止敏感信息泄露。
    """
    # 1. 为开发人员记录详细的、包含完整堆栈跟踪的错误日志
    l.exception(
        f"An unhandled exception occurred for request: {request.method} {request.url.path}"
    )

    raise_internal_error()

# --- Security ---
async def verify_token(x_auth_token: str = Header()):
    if x_auth_token != config.AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing authentication token")

# --- API Endpoints ---
@app.post(
    "/execute",
    dependencies=[Depends(verify_token)],
)
async def execute(request: ExecuteRequest) -> ExecuteResponse:
    worker = await WorkerManager.get_worker_for_user(request.user_uuid)
    if not worker:
        raise HTTPException(status_code=503, detail="No available workers at the moment, please try again later.")

    # Proxy the request to the assigned worker
    try:
        async with httpx.AsyncClient() as client:
            worker_request_body = {"code": request.code}
            response = await client.post(
                f"{worker.internal_url}/execute",
                json=worker_request_body,
                timeout=30.0 # A reasonable timeout for the whole operation
            )
            # Forward the worker's response (both success and error)
            if response.status_code != 200:
                error_detail = response.json().get("detail", "Worker returned an unknown error.")
                raise HTTPException(status_code=response.status_code, detail=error_detail)
            return ExecuteResponse(**response.json())
    except httpx.RequestError as e:
        l.error(f"Failed to proxy request to worker {worker.container_name}: {e}")
        await WorkerManager.release_worker_by_user(request.user_uuid)
        raise HTTPException(status_code=504, detail="Gateway Timeout: Could not connect to the execution worker.")
    except HTTPException as he:
        raise
    except Exception as e:
        l.exception(e)
        await WorkerManager.release_worker_by_user(request.user_uuid)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.post("/release", response_model=ReleaseResponse, dependencies=[Depends(verify_token)])
async def release(request: ReleaseRequest):
    await WorkerManager.release_worker_by_user(request.user_uuid)
    return ReleaseResponse(status="ok", detail=f"Worker for user {request.user_uuid} has been released.")

@app.get("/status")
async def get_status():
    return {
        "total_workers": len(WorkerManager.workers),
        "busy_workers": len(WorkerManager.user_to_worker_map),
        "idle_workers_in_pool": WorkerManager.idle_workers.qsize(),
        "is_initializing": WorkerManager._is_initializing,
    }

```

--- 

`gateway\requirements.txt`

```
fastapi
uvicorn[standard]
loguru
httpx
pydantic
aiodocker

```

--- 

`gateway\utils.py`

```python
from typing import Any, NoReturn, TYPE_CHECKING

from fastapi import HTTPException

from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_501_NOT_IMPLEMENTED,
    HTTP_503_SERVICE_UNAVAILABLE,
    HTTP_504_GATEWAY_TIMEOUT, HTTP_402_PAYMENT_REQUIRED,
)

# --- Request and Response Helpers ---

def ensure_request_param(to_check: Any, detail: str) -> None:
    """
    Ensures a parameter exists. If not, raises a 400 Bad Request.
    This function returns None if the check passes.
    """
    if not to_check:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=detail)

def raise_bad_request(detail: str = '') -> NoReturn:
    """Raises an HTTP 400 Bad Request exception."""
    raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=detail)

def raise_not_found(detail: str) -> NoReturn:
    """Raises an HTTP 404 Not Found exception."""
    raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=detail)

def raise_internal_error(detail: str = "服务器出现故障，请稍后再试或联系管理员") -> NoReturn:
    """Raises an HTTP 500 Internal Server Error exception."""
    raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)

def raise_forbidden(detail: str) -> NoReturn:
    """Raises an HTTP 403 Forbidden exception."""
    raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail=detail)

def raise_unauthorized(detail: str) -> NoReturn:
    """Raises an HTTP 401 Unauthorized exception."""
    raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail=detail)

def raise_conflict(detail: str) -> NoReturn:
    """Raises an HTTP 409 Conflict exception."""
    raise HTTPException(status_code=HTTP_409_CONFLICT, detail=detail)

def raise_too_many_requests(detail: str) -> NoReturn:
    """Raises an HTTP 429 Too Many Requests exception."""
    raise HTTPException(status_code=HTTP_429_TOO_MANY_REQUESTS, detail=detail)

def raise_not_implemented(detail: str = "尚未支持这种方法") -> NoReturn:
    """Raises an HTTP 501 Not Implemented exception."""
    raise HTTPException(status_code=HTTP_501_NOT_IMPLEMENTED, detail=detail)

def raise_service_unavailable(detail: str) -> NoReturn:
    """Raises an HTTP 503 Service Unavailable exception."""
    raise HTTPException(status_code=HTTP_503_SERVICE_UNAVAILABLE, detail=detail)

def raise_gateway_timeout(detail: str) -> NoReturn:
    """Raises an HTTP 504 Gateway Timeout exception."""
    raise HTTPException(status_code=HTTP_504_GATEWAY_TIMEOUT, detail=detail)

def raise_insufficient_quota(detail: str = "积分不足，请充值") -> NoReturn:
    raise HTTPException(status_code=HTTP_402_PAYMENT_REQUIRED, detail=detail)

# --- End of Request and Response Helpers ---

```

--- 

`gateway\worker_manager.py`

```python
import asyncio
import time
import uuid

import httpx
from aiodocker.containers import DockerContainer
from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError
from fastapi import HTTPException
from loguru import logger as l

from dto import Worker, WorkerStatus


class WorkerManager:
    """
    Manages the lifecycle of Docker-based worker containers.

    This class is implemented as a Singleton using only class-level variables
    and methods. It handles the creation, assignment, and destruction of
    workers, maintaining a pool of idle workers to handle user requests
    promptly.
    """
    # --- Configuration variables ---
    # These must be set by calling the `init` method before use.
    WORKER_IMAGE_NAME: str
    INTERNAL_NETWORK_NAME: str
    MIN_IDLE_WORKERS: int
    MAX_TOTAL_WORKERS: int
    WORKER_IDLE_TIMEOUT: int
    RECYCLING_INTERVAL: int

    # --- Internal state ---
    docker: Docker = Docker()
    workers: dict[str, Worker] = {}  # container_id -> Worker
    user_to_worker_map: dict[str, str] = {}  # user_uuid -> container_id
    idle_workers: asyncio.Queue[Worker] = asyncio.Queue()
    _lock: asyncio.Lock = asyncio.Lock()
    _is_initializing: bool = True

    @classmethod
    async def init(
        cls,
        worker_image_name: str,
        internal_network_name: str,
        min_idle_workers: int,
        max_total_workers: int,
        worker_idle_timeout: int,
        recycling_interval: int,
    ) -> None:
        """
        Injects configuration and initializes the worker pool.

        Cleans up any stale worker containers from previous runs and
        pre-warms the pool by creating a minimum number of idle workers.
        """
        # 1. Configure the manager
        cls.WORKER_IMAGE_NAME = worker_image_name
        cls.INTERNAL_NETWORK_NAME = internal_network_name
        cls.MIN_IDLE_WORKERS = min_idle_workers
        cls.MAX_TOTAL_WORKERS = max_total_workers
        cls.WORKER_IDLE_TIMEOUT = worker_idle_timeout
        cls.RECYCLING_INTERVAL = recycling_interval

        # 2. Initialize the pool
        l.info("Initializing worker pool...")
        await cls._cleanup_stale_workers()
        await cls._replenish_idle_pool()
        cls._is_initializing = False
        l.info(f"Worker pool initialized. Idle workers: {cls.idle_workers.qsize()}")

    @classmethod
    async def close(cls) -> None:
        """Closes the Docker client connection."""
        await cls.docker.close()

    @classmethod
    async def _cleanup_stale_workers(cls) -> None:
        """Finds and removes any dangling worker containers managed by this gateway."""
        try:
            old_workers: list[DockerContainer] = await cls.docker.containers.list(
                filters={"label": [f"managed-by=code-interpreter-gateway"]},
            )
            if not old_workers:
                return

            l.warning(f"Found {len(old_workers)} stale worker containers. Cleaning up...")
            cleanup_tasks = [container.delete(force=True) for container in old_workers]
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            l.info("Stale worker cleanup complete.")
        except DockerError as e:
            l.error(f"Error during stale worker cleanup: {e}")

    @classmethod
    async def _create_new_worker(cls) -> Worker:
        """
        Creates, starts, and health-checks a single new worker container.

        :return: A healthy Worker object or None if creation fails.
        """
        container_name = f"code-worker-{uuid.uuid4().hex[:12]}"
        try:
            l.info(f"Creating new worker container: {container_name}")
            container: DockerContainer = await cls.docker.containers.create_or_replace(
                config={
                    'Image': cls.WORKER_IMAGE_NAME,
                    'HostConfig': {
                        'NetworkMode': cls.INTERNAL_NETWORK_NAME,
                    },
                    'Labels': {'managed-by': "code-interpreter-gateway"},
                },
                name=container_name,
            )
            await container.start()

            worker = Worker(
                container_id=container.id,
                container_name=container_name,
                internal_url=f"http://{container_name}:8000",
                status=WorkerStatus.IDLE,
            )

            is_healthy = await cls._is_worker_healthy(worker)
            if not is_healthy:
                l.error(f"Newly created worker {container_name} is unhealthy. Removing.")
                await cls._destroy_worker(worker)
                raise RuntimeError("Worker failed health check after creation.")

            l.success(f"Worker {container_name} created and healthy.")
            return worker
        except DockerError as e:
            msg = f"Failed to create container {container_name}: {e}"
            l.error(msg)
            raise RuntimeError(msg)

    @classmethod
    async def _is_worker_healthy(cls, worker: Worker, timeout: int = 30) -> bool:
        """
        Performs a health check on a worker by polling its /health endpoint.

        :param worker: The worker to check.
        :param timeout: The maximum time in seconds to wait for the worker to become healthy.
        :return: True if the worker is healthy, False otherwise.
        """
        start_time = time.time()
        async with httpx.AsyncClient() as client:
            while time.time() - start_time < timeout:
                try:
                    response = await client.get(f"{worker.internal_url}/health", timeout=2.0)
                    if response.status_code == 200:
                        return True
                except httpx.RequestError:
                    await asyncio.sleep(0.1)
            return False

    @classmethod
    async def _destroy_worker(cls, worker: Worker) -> None:
        """
        Stops and removes a worker's Docker container and cleans up internal state.

        :param worker: The worker to destroy.
        """
        l.warning(f"Destroying worker: {worker.container_name}")
        try:
            container: DockerContainer = cls.docker.containers.container(worker.container_id)
            await container.delete(force=True)
        except DockerError as e:
            if e.status == 404:
                l.warning(f"Worker {worker.container_name} not found.")
            else:
                msg = f"Error deleting container {worker.container_name}: {e}"
                l.error(msg)
                raise RuntimeError(msg)
        finally:
            # Clean up internal state
            cls.workers.pop(worker.container_id, None)
            if worker.user_uuid and worker.user_uuid in cls.user_to_worker_map:
                cls.user_to_worker_map.pop(worker.user_uuid, None)

    @classmethod
    async def get_worker_for_user(cls, user_uuid: str) -> Worker:
        """
        Gets a worker for a given user.

        Retrieves an existing worker, an idle worker from the pool, or creates
        a new one.

        :param user_uuid: The UUID of the user requesting a worker.
        :return: An available Worker instance.
        :raises HTTPException: If the pool is initializing or no worker is available.
        """
        async with cls._lock:
            if cls._is_initializing:
                raise HTTPException(
                    status_code=503,
                    detail="Worker pool is initializing. Please try again shortly.",
                )

            # Case 1: User already has an active worker
            if user_uuid in cls.user_to_worker_map:
                container_id = cls.user_to_worker_map[user_uuid]
                worker = cls.workers[container_id]
                worker.last_active_timestamp = time.time()
                l.info(f"Found existing worker {worker.container_name} for user {user_uuid}")
                return worker

            # Case 2: Get an idle worker from the pool
            if not cls.idle_workers.empty():
                worker = await cls.idle_workers.get()
                cls._bind_worker_to_user(worker, user_uuid)
                l.info(f"Assigned idle worker {worker.container_name} to user {user_uuid}")
                return worker

            # Case 3: Create a new worker if under the configured maximum limit
            if len(cls.workers) < cls.MAX_TOTAL_WORKERS:
                l.info("No idle workers available. Attempting to create a new one.")
                worker = await cls._create_new_worker()
                if worker:
                    cls.workers[worker.container_id] = worker
                    cls._bind_worker_to_user(worker, user_uuid)
                    l.info(
                        f"Assigned newly created worker {worker.container_name} to user {user_uuid}"
                    )
                    return worker

            # Case 4: Max limit reached, no workers available
            raise HTTPException(status_code=503, detail="No available workers. Please try again later.")

    @classmethod
    def _bind_worker_to_user(cls, worker: Worker, user_uuid: str) -> None:
        """
        Assigns a worker to a user and updates its state.

        :param worker: The worker to be assigned.
        :param user_uuid: The user's UUID.
        """
        worker.status = WorkerStatus.BUSY
        worker.user_uuid = user_uuid
        worker.last_active_timestamp = time.time()
        cls.user_to_worker_map[user_uuid] = worker.container_id

    @classmethod
    async def release_worker_by_user(cls, user_uuid: str) -> None:
        """
        Releases a worker previously assigned to a user.

        This method destroys the worker container and triggers pool replenishment.

        :param user_uuid: The UUID of the user releasing the worker.
        """
        async with cls._lock:
            if user_uuid not in cls.user_to_worker_map:
                return

            container_id = cls.user_to_worker_map.pop(user_uuid)
            worker = cls.workers.pop(container_id)
            l.info(f"User {user_uuid} released worker {worker.container_name}. Destroying...")
            await cls._destroy_worker(worker)
            await cls._replenish_idle_pool()

    @classmethod
    async def _replenish_idle_pool(cls) -> None:
        """
        Creates new workers to meet the minimum idle worker requirement.

        This function should always be called within a lock to ensure thread safety.
        """
        needed_count = cls.MIN_IDLE_WORKERS - cls.idle_workers.qsize()
        available_slots = cls.MAX_TOTAL_WORKERS - len(cls.workers)

        creation_count = min(needed_count, available_slots)
        if creation_count <= 0:
            return

        l.info(f"Replenishing idle pool. Need to create {creation_count} worker(s).")
        tasks = [cls._create_new_worker() for _ in range(creation_count)]
        new_workers = await asyncio.gather(*tasks)

        for worker in new_workers:
            if worker:
                cls.workers[worker.container_id] = worker
                await cls.idle_workers.put(worker)

    @classmethod
    async def recycle_timed_out_workers(cls) -> None:
        """
        Periodically checks for and recycles workers that have been idle for too long.

        This method is designed to be run as a continuous background task.
        """
        while True:
            await asyncio.sleep(cls.RECYCLING_INTERVAL)
            async with cls._lock:
                l.info("Running background task to recycle timed-out workers...")
                now = time.time()
                timed_out_users: list[str] = []
                for user_uuid, container_id in cls.user_to_worker_map.items():
                    worker = cls.workers.get(container_id)
                    if worker and (now - worker.last_active_timestamp > cls.WORKER_IDLE_TIMEOUT):
                        timed_out_users.append(user_uuid)

                if timed_out_users:
                    l.warning(f"Found {len(timed_out_users)} timed-out workers to recycle.")
                    for user_uuid in timed_out_users:
                        container_id = cls.user_to_worker_map.pop(user_uuid)
                        worker = cls.workers.pop(container_id)
                        await cls._destroy_worker(worker)

                    await cls._replenish_idle_pool()
                else:
                    l.info("No timed-out workers found.")

```

--- 

`start.ps1`

```
# start.ps1

# 设置脚本在遇到错误时立即停止
$ErrorActionPreference = "Stop"

Write-Host "🚀 [Step 1/2] Starting the Code Interpreter environment..." -ForegroundColor Green
# 使用 --build 确保镜像总是最新的
# 使用 -d 在后台运行
docker-compose up --build -d

# 检查上一个命令是否成功
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ docker-compose up failed. Please check the logs." -ForegroundColor Red
    exit 1
}

Write-Host "✅ Environment started. Gateway is running." -ForegroundColor Green
Write-Host "🧹 [Step 2/2] Cleaning up the temporary builder container..." -ForegroundColor Cyan

# 查找名为 code-interpreter_worker_builder 的容器
$builderId = docker ps -a -q --filter "name=code-interpreter_worker_builder"

if ($builderId) {
    Write-Host "   -> Found builder container. Removing it..."
    docker rm $builderId | Out-Null
    Write-Host "   -> Builder container successfully removed." -ForegroundColor Green
} else {
    Write-Host "   -> No temporary builder container found to clean up. Skipping." -ForegroundColor Yellow
}

Write-Host "🎉 Startup complete. The system is ready."

```

--- 

`stop.ps1`

```
# stop.ps1

# 设置脚本在遇到错误时继续执行，因为我们预期某些命令可能会“失败”
$ErrorActionPreference = "SilentlyContinue"

Write-Host "🛑 Initiating shutdown sequence for the Code Interpreter environment..." -ForegroundColor Yellow

Write-Host "🤚 [Step 1/3] Stopping the gateway container to prevent new workers..." -ForegroundColor Cyan
# 第一次 down 会停止并移除 gateway。网络删除失败是正常的。
docker-compose down
Write-Host "   -> Gateway stopped."

Write-Host "🔥 [Step 2/3] Finding and forcibly removing all dynamically created workers..." -ForegroundColor Cyan
$workerIds = docker ps -a -q --filter "label=managed-by=code-interpreter-gateway"

if ($workerIds) {
    Write-Host "   -> Found running worker containers. Removing them now..."
    docker rm -f $workerIds | Out-Null
    Write-Host "   -> All dynamic workers have been removed." -ForegroundColor Green
} else {
    Write-Host "   -> No dynamically created workers found." -ForegroundColor Yellow
}

Write-Host "🧹 [Step 3/3] Final cleanup to remove the network..." -ForegroundColor Cyan
# 因为 worker 已经被清理，这次 down 将成功移除网络
docker-compose down
Write-Host "   -> Network and remaining resources cleaned up."

Write-Host "✅ Shutdown and cleanup complete." -ForegroundColor Green


```

--- 

`test.html`

```
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Interpreter API Test Client</title>
    <style>
        :root {
            --bg-color: #f8f9fa;
            --text-color: #212529;
            --primary-color: #0d6efd;
            --border-color: #dee2e6;
            --pre-bg-color: #e9ecef;
            --error-color: #dc3545;
            --success-color: #198754;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: var(--bg-color);
            color: var(--text-color);
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .container {
            width: 100%;
            max-width: 800px;
            background: #fff;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }
        h1, h2 {
            text-align: center;
            color: #333;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            font-weight: 600;
            margin-bottom: 5px;
        }
        input[type="text"], textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            box-sizing: border-box;
            font-size: 16px;
        }
        textarea {
            height: 200px;
            font-family: Consolas, "Courier New", monospace;
            resize: vertical;
        }
        .button-group {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        button {
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            background-color: var(--primary-color);
            color: white;
            font-size: 16px;
            cursor: pointer;
            transition: background-color 0.2s;
            flex-grow: 1;
        }
        button:hover {
            background-color: #0b5ed7;
        }
        button:disabled {
            background-color: #6c757d;
            cursor: not-allowed;
        }
        button.secondary {
            background-color: #6c757d;
        }
        button.secondary:hover {
            background-color: #5c636a;
        }
        #session-controls {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        #session-controls input {
            flex-grow: 1;
        }
        #output-log {
            margin-top: 25px;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 15px;
            height: 400px;
            overflow-y: auto;
            background-color: var(--bg-color);
        }
        .log-entry {
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 1px dashed var(--border-color);
        }
        .log-entry:last-child {
            border-bottom: none;
        }
        pre {
            background-color: var(--pre-bg-color);
            padding: 10px;
            border-radius: 4px;
            white-space: pre-wrap;
            word-wrap: break-word;
            margin: 5px 0;
        }
        .log-input pre {
            background-color: #dbeafe;
        }
        .log-output pre, .log-output img {
            background-color: #e9ecef;
        }
        .log-error pre {
            background-color: #f8d7da;
            color: var(--error-color);
        }
        .log-status {
            font-style: italic;
            color: #6c757d;
        }
        img.result-image {
            max-width: 100%;
            height: auto;
            border: 1px solid var(--border-color);
            margin-top: 10px;
            display: block;
        }
    </style>
</head>
<body>

<div class="container">
    <h1>Code Interpreter Test Client</h1>

    <h2>1. Configuration</h2>
    <div class="form-group">
        <label for="gateway-url">Gateway URL</label>
        <input type="text" id="gateway-url" value="http://127.0.0.1:3874">
    </div>
    <div class="form-group">
        <label for="auth-token">Auth Token (X-Auth-Token)</label>
        <input type="text" id="auth-token" placeholder="Paste your token here">
    </div>
    <div class="form-group">
        <label for="user-uuid">Current Session UUID</label>
        <div id="session-controls">
            <input type="text" id="user-uuid" readonly>
            <button id="regenerate-uuid" class="secondary" title="Start a new session">New Session</button>
        </div>
    </div>

    <h2>2. Code Execution</h2>
    <div class="form-group">
        <label for="code-input">Python Code</label>
        <textarea id="code-input" placeholder="a = 10&#10;b = 20&#10;print(f'The sum is {a + b}')"></textarea>
    </div>
    <div class="button-group">
        <button id="run-button">Run Code</button>
        <button id="release-button" class="secondary">Release Session</button>
    </div>

    <h2>3. Session Log</h2>
    <div id="output-log">
        <div class="log-status">Ready to execute code...</div>
    </div>
</div>

<script>
    // --- DOM Elements ---
    const gatewayUrlInput = document.getElementById('gateway-url');
    const authTokenInput = document.getElementById('auth-token');
    const userUuidInput = document.getElementById('user-uuid');
    const codeInput = document.getElementById('code-input');
    const runButton = document.getElementById('run-button');
    const releaseButton = document.getElementById('release-button');
    const regenerateUuidButton = document.getElementById('regenerate-uuid');
    const outputLog = document.getElementById('output-log');

    // --- Functions ---

    /** Generates a v4 UUID */
    function generateUUID() {
        return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
            (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
        );
    }

    /** Clears the log and adds a message */
    function clearLog(message) {
        outputLog.innerHTML = `<div class="log-status">${message}</div>`;
    }

    /** Appends a new entry to the log */
    function appendToLog(entry) {
        const isScrolledToBottom = outputLog.scrollHeight - outputLog.clientHeight <= outputLog.scrollTop + 1;

        const firstEntry = outputLog.querySelector('.log-status');
        if (firstEntry) {
            outputLog.innerHTML = '';
        }
        outputLog.appendChild(entry);

        if (isScrolledToBottom) {
            outputLog.scrollTop = outputLog.scrollHeight;
        }
    }

    /** Creates a log entry element */
    function createLogEntry(code, resultElement) {
        const entryDiv = document.createElement('div');
        entryDiv.className = 'log-entry';

        const inputHeader = document.createElement('strong');
        inputHeader.textContent = 'Input Code:';
        const inputPre = document.createElement('pre');
        inputPre.textContent = code;
        const inputDiv = document.createElement('div');
        inputDiv.className = 'log-input';
        inputDiv.append(inputHeader, inputPre);

        const outputHeader = document.createElement('strong');
        outputHeader.textContent = 'Result:';
        const outputDiv = document.createElement('div');
        // 【修正】根据 resultElement 是否有 'log-error' class 来决定父 div 的 class
        outputDiv.className = resultElement.classList.contains('log-error') ? 'log-error' : 'log-output';
        outputDiv.append(outputHeader, resultElement);

        entryDiv.append(inputDiv, outputDiv);
        return entryDiv;
    }

    /** Handles code execution */
    async function handleExecute() {
        // 【修正】为所有输入都添加 .trim() 增加健壮性
        const gatewayUrl = gatewayUrlInput.value.trim();
        const authToken = authTokenInput.value.trim();
        const userUuid = userUuidInput.value.trim();
        const code = codeInput.value.trim();

        if (!gatewayUrl || !authToken || !userUuid || !code) {
            alert('Please fill in all fields: Gateway URL, Auth Token, and Code.');
            return;
        }

        runButton.disabled = true;
        runButton.textContent = 'Executing...';

        let resultElement;
        try {
            const response = await fetch(`${gatewayUrl}/execute`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Auth-Token': authToken
                },
                body: JSON.stringify({
                    user_uuid: userUuid,
                    code: code
                })
            });

            const data = await response.json();

            if (!response.ok) {
                resultElement = document.createElement('pre');
                // 【修正】直接给 resultElement 本身添加 class，而不是给它不存在的 parentElement
                resultElement.classList.add('log-error');
                resultElement.textContent = `Error ${response.status}: ${data.detail || JSON.stringify(data)}`;
            } else {
                if (data.result_base64) {
                    resultElement = document.createElement('img');
                    resultElement.className = 'result-image';
                    resultElement.src = `data:image/png;base64,${data.result_base64}`;
                } else {
                    resultElement = document.createElement('pre');
                    resultElement.textContent = data.result_text ?? '(No text output)';
                }
            }
        } catch (error) {
            resultElement = document.createElement('pre');
            // 【修正】同样，直接给 resultElement 本身添加 class
            resultElement.classList.add('log-error');
            resultElement.textContent = `Network or fetch error: ${error.message}`;
        } finally {
            runButton.disabled = false;
            runButton.textContent = 'Run Code';
            if (resultElement) { // 确保 resultElement 存在
                const logEntry = createLogEntry(code, resultElement);
                appendToLog(logEntry);
            }
        }
    }

    /** Handles session release */
    async function handleRelease() {
        const gatewayUrl = gatewayUrlInput.value.trim();
        const authToken = authTokenInput.value.trim();
        const userUuid = userUuidInput.value.trim();

        if (!gatewayUrl || !authToken || !userUuid) {
            alert('Please provide Gateway URL and Auth Token.');
            return;
        }

        releaseButton.disabled = true;
        releaseButton.textContent = 'Releasing...';
        try {
            const response = await fetch(`${gatewayUrl}/release`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Auth-Token': authToken
                },
                body: JSON.stringify({ user_uuid: userUuid })
            });

            const data = await response.json();
            const message = response.ok ? `Success: ${data.detail}` : `Error: ${data.detail}`;
            clearLog(`Session ${userUuid} released. ${message}. Start a new session by clicking 'New Session'.`);

        } catch (error) {
            alert(`Failed to release session: ${error.message}`);
        } finally {
            releaseButton.disabled = false;
            releaseButton.textContent = 'Release Session';
        }
    }

    /** Starts a new session */
    function startNewSession() {
        userUuidInput.value = generateUUID();
        clearLog(`New session started with UUID: ${userUuidInput.value}. Ready to execute code...`);
    }

    // --- Event Listeners ---
    document.addEventListener('DOMContentLoaded', startNewSession);
    runButton.addEventListener('click', handleExecute);
    releaseButton.addEventListener('click', handleRelease);
    regenerateUuidButton.addEventListener('click', startNewSession);

</script>
</body>
</html>

```

--- 

`worker\Dockerfile`

```
# worker/Dockerfile

FROM python:3.12-slim-bookworm

LABEL maintainer="Foxerine"
LABEL description="A self-contained, secure, stateful Python code interpreter WORKER."

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1

# [新增] 创建沙箱目录，这将是代码执行的默认工作区
RUN mkdir /sandbox

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends supervisor tini fontconfig libgl1-mesa-glx libglib2.0-0 curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install font
COPY ./assets/simhei.ttf /usr/share/fonts/truetype/
RUN fc-cache -fv

# Install Python dependencies
WORKDIR /worker
# [更新] 将 PYTHONPATH 设置为 /worker，以便在 /sandbox 中也能导入应用代码
ENV PYTHONPATH=/worker
COPY ./requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

RUN ipython kernel install --name "python3" --user

# Copy application code & configs
COPY . /worker
COPY ./supervisor/supervisord.conf /etc/supervisor/supervisord.conf

# [更新] 将最终的工作目录切换到沙箱
WORKDIR /sandbox

EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]

```

--- 

`worker\dto.py`

```python
"""Data Transfer Objects (DTOs) for the Python Code Interpreter API."""
from typing import Literal

from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    """Defines the structure for a Python code execution request."""
    code: str


class ExecuteResponse(BaseModel):
    """Defines the structure for a code execution response."""
    result_text: str | None = None
    result_base64: str | None = None


class HealthDetail(BaseModel):
    """Describes the health status of a single internal service."""
    status: str
    detail: str


class HealthStatus(BaseModel):
    """Describes the overall health of the container."""
    status: str
    services: dict[str, HealthDetail]

class ExecutionResult(BaseModel):
    """代码执行结果的 DTO"""
    status: Literal["ok", "error", "timeout"]
    type: Literal["text", "image_png_base64", "connection_error", "execution_error", "timeout_error", "processing_error"]
    value: str | None = None

```

--- 

`worker\kernel_manager.py`

```python
# worker/kernel_manager.py

"""
Manages the lifecycle and interaction with a stateful Jupyter Kernel.
This module is fully compliant with the websockets library's best practices.
"""
import asyncio
import json
import time
from uuid import uuid4
from xmlrpc.client import ServerProxy

import httpx
from loguru import logger as l
from websockets.asyncio.client import connect, ClientConnection
from websockets.exceptions import ConnectionClosed, WebSocketException
from websockets.protocol import OPEN

from dto import ExecutionResult


class JupyterKernelManager:
    """A static manager for a persistent Jupyter Kernel."""
    # --- Constants ---
    JUPYTER_HOST: str = "127.0.0.1:8888"
    JUPYTER_API_URL: str = f"http://{JUPYTER_HOST}"
    JUPYTER_WS_URL: str = f"ws://{JUPYTER_HOST}"
    EXECUTION_TIMEOUT: float = 10.0

    _MATPLOTLIB_FONT_PREP_CODE: str = (
        "import matplotlib\n"
        "matplotlib.rcParams['font.family'] = ['SimHei']\n"
        "matplotlib.rcParams['axes.unicode_minus'] = False\n"
    )

    # --- State ---
    _kernel_id: str | None = None
    _ws_connection: ClientConnection | None = None
    _lock = asyncio.Lock()
    _supervisor = ServerProxy('http://127.0.0.1:9001/RPC2')

    @classmethod
    async def start_kernel(cls) -> None:
        """启动并连接到一个新的 Jupyter Kernel 实例，带有重试机制以提高启动稳定性。"""
        if cls._kernel_id:
            l.warning("Kernel 已经启动。")
            return

        l.info("正在尝试启动并连接到新的 Jupyter Kernel...")
        max_retries = 10
        retry_delay = 1.0  # seconds

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(
                        url=f'{cls.JUPYTER_API_URL}/api/kernels',
                        json={'name': "python"},
                        headers={'Content-Type': 'application/json'}
                    )
                    response.raise_for_status()
                    kernel_data = response.json()
                    cls._kernel_id = kernel_data['id']
                    l.success(f"🚀 Jupyter Kernel 已成功创建, ID: {cls._kernel_id}")
                    await cls._establish_websocket_connection()

                    l.info("正在初始化 Kernel 环境...")
                    init_result = await cls.execute_code(cls._MATPLOTLIB_FONT_PREP_CODE, is_initialization=True)
                    if init_result.status != "ok":
                        l.error(f"🔥 Kernel 环境初始化失败: {init_result.value}")
                        await cls._shutdown_kernel()
                        raise RuntimeError("Kernel 环境初始化失败。")
                    l.success("✅ Kernel 环境初始化成功。")
                    return
            except httpx.RequestError as e:
                l.warning(f"无法连接到 Jupyter Server (尝试 {attempt + 1}/{max_retries}): {e}。将在 {retry_delay} 秒后重试...")
                await asyncio.sleep(retry_delay)
            except Exception:
                await cls._shutdown_kernel()
                raise

        l.error(f"🔥 启动 Jupyter Kernel 失败，已达到最大重试次数 ({max_retries})。")
        raise RuntimeError("无法连接到 Jupyter Server。请检查 Jupyter 服务的日志。")

    @classmethod
    async def _shutdown_kernel(cls):
        """关闭并清理当前的 kernel。"""
        if not cls._kernel_id:
            return
        kernel_id = cls._kernel_id
        cls._kernel_id = None
        l.warning(f"正在关闭 Kernel {kernel_id}...")
        try:
            if cls._ws_connection and cls._ws_connection.state is OPEN:
                await cls._ws_connection.close()
            cls._ws_connection = None

            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.delete(f'{cls.JUPYTER_API_URL}/api/kernels/{kernel_id}')
            l.info(f"Kernel {kernel_id} 已成功关闭。")
        except httpx.RequestError as e:
            l.warning(f"关闭 kernel {kernel_id} 时出错: {e}")
        except Exception as e:
            l.error(f"关闭 kernel {kernel_id} 时发生意外错误: {e}")

    @classmethod
    async def _establish_websocket_connection(cls) -> None:
        """建立到 Kernel 的 WebSocket 连接"""
        if cls._ws_connection and cls._ws_connection.state is OPEN:
            await cls._ws_connection.close()
        try:
            cls._ws_connection = await connect(
                uri=f'{cls.JUPYTER_WS_URL}/api/kernels/{cls._kernel_id}/channels'
            )
            l.info("🔌 已建立到 Kernel 的 WebSocket 连接。")
        except WebSocketException as e:
            l.error(f"🔥 建立 WebSocket 连接失败: {e}")
            cls._ws_connection = None
            raise

    @classmethod
    async def is_healthy(cls) -> bool:
        """检查 WebSocket 连接是否健康"""
        if cls._ws_connection is None or cls._ws_connection.state is not OPEN:
            return False
        try:
            await asyncio.wait_for(cls._ws_connection.ping(), timeout=2.0)
            return True
        except (asyncio.TimeoutError, ConnectionClosed, WebSocketException):
            return False

    @classmethod
    async def reset_kernel(cls) -> bool:
        """通过 Supervisor 重启 Kernel 进程来重置它"""
        l.warning("🚨 正在重置 Jupyter Kernel...")
        async with cls._lock:
            process_name = 'jupyter_kernel'
            try:
                cls._supervisor.supervisor.stopProcess(process_name)
                l.info(f"🛑 {process_name} 进程已停止。")
                for _ in range(10): # 等待最多10秒
                    await asyncio.sleep(1)
                    state_info = cls._supervisor.supervisor.getProcessInfo(process_name)
                    if state_info['state'] == 20:  # RUNNING
                        l.info(f"✅ {process_name} 进程已由 Supervisor 重启。")
                        # 清理旧状态并重新初始化
                        cls._kernel_id = None
                        if cls._ws_connection:
                            await cls._ws_connection.close()
                        cls._ws_connection = None
                        await cls.start_kernel()
                        return True
                l.error(f"🔥 {process_name} 未能在时限内重启。")
                return False
            except Exception as e:
                l.error(f"🔥 Kernel 重置过程中发生错误: {e}")
                return False


    @classmethod
    async def execute_code(cls, code: str, is_initialization: bool = False) -> ExecutionResult:
        """在 Kernel 中执行代码并返回结果"""
        if not is_initialization:
            code_preview = (code[:97] + '...' if len(code) > 100 else code).replace('\n', ' ')
            l.info(f"▶️  准备执行代码: {code_preview.strip()}")
            start_time = time.monotonic()

        escaped_code = json.dumps(code)[1:-1]

        async with cls._lock:
            if not await cls.is_healthy():
                l.warning("WebSocket 连接不健康，正在尝试重连...")
                try:
                    await cls._establish_websocket_connection()
                except WebSocketException:
                    return ExecutionResult(status="error", type='connection_error', value="执行引擎连接丢失。")

            assert cls._ws_connection is not None
            msg_id = uuid4().hex
            execute_request = f'''
            {{
                "header": {{
                    "msg_id": "{msg_id}", "username": "api", "session": "{uuid4().hex}",
                    "msg_type": "execute_request", "version": "5.3"
                }},
                "parent_header": {{}}, "metadata": {{}},
                "content": {{
                    "code": "{escaped_code}", "silent": false, "store_history": false,
                    "user_expressions": {{}}, "allow_stdin": false
                }}, "buffers": [], "channel": "shell"
            }}
            '''
            try:
                await cls._ws_connection.send(execute_request)
                # [更新] 使用新的消息处理函数
                result = await asyncio.wait_for(
                    cls._process_execution_messages(msg_id),
                    timeout=cls.EXECUTION_TIMEOUT
                )
            except asyncio.TimeoutError:
                l.warning(f"代码执行超时（超过 {cls.EXECUTION_TIMEOUT} 秒）。")
                result = ExecutionResult(
                    status="timeout", type='timeout_error',
                    value=f"代码执行超时（超过 {cls.EXECUTION_TIMEOUT} 秒）。"
                )
            except ConnectionClosed:
                l.error("连接在发送前或发送过程中被关闭。")
                result = ExecutionResult(status="error", type='connection_error', value="执行引擎连接丢失。")

            if not is_initialization:
                end_time = time.monotonic()
                duration = (end_time - start_time) * 1000
                l.info(f"⏹️  代码执行完成. 状态: {result.status.upper()}, 耗时: {duration:.2f} ms")

            return result

    @classmethod
    async def _process_execution_messages(cls, msg_id: str) -> ExecutionResult:
        """
        [重构] 处理从 Kernel 返回的所有消息，直到执行状态变为空闲。
        这个新版本会累积结果，优先返回图像。
        """
        assert cls._ws_connection is not None

        result_text_parts = []
        result_base64 = None
        error_output = None

        while True:
            try:
                message_raw = await cls._ws_connection.recv()
                msg = json.loads(message_raw)
                l.debug(msg)

                if msg.get("parent_header", {}).get("msg_id") != msg_id:
                    continue

                msg_type = msg["msg_type"]
                content = msg.get("content", {})

                if msg_type == 'stream':
                    result_text_parts.append(content.get('text', ''))

                elif msg_type == 'execute_result':
                    result_text_parts.append(content.get('data', {}).get('text/plain', ''))

                elif msg_type == 'display_data':
                    if 'image/png' in content.get('data', {}):
                        # 优先保留图片结果
                        result_base64 = content['data']['image/png']

                elif msg_type == 'error':
                    error_output = f"{content.get('ename', 'Error')}: {content.get('evalue', '')}"
                    # 出现错误，可以提前退出循环
                    break

                elif msg_type == 'status' and content.get('execution_state') == 'idle':
                    # 这是执行结束的信号，退出循环
                    break

            except (ConnectionClosed, WebSocketException) as e:
                return ExecutionResult(status="error", type='connection_error',
                                       value=f"执行引擎连接丢失: {type(e).__name__}")
            except Exception as e:
                return ExecutionResult(status="error", type='processing_error', value=f"发生意外的处理错误: {e}")

        # -- 循环结束后，根据收集到的结果决定最终返回值 --
        if error_output:
            return ExecutionResult(status="error", type='execution_error', value=error_output)

        if result_base64:
            return ExecutionResult(status="ok", type='image_png_base64', value=result_base64)

        final_text = "".join(result_text_parts)
        return ExecutionResult(status="ok", type='text', value=final_text)

```

--- 

`worker\main.py`

```python
"""
Main FastAPI application for the Python Code Interpreter WORKER service.
Authentication is handled by the Gateway. This service is not exposed publicly.
"""
import asyncio
from fastapi import FastAPI, HTTPException, status
from loguru import logger as l

from dto import ExecuteRequest, ExecuteResponse
from kernel_manager import JupyterKernelManager

# --- Application Lifecycle ---
async def _lifespan(app: FastAPI):
    l.info("Worker is starting up...")
    await JupyterKernelManager.start_kernel()
    yield
    l.info("Worker is shutting down...")

# --- FastAPI Application Instance ---
app = FastAPI(
    title="Python Code Interpreter Worker",
    lifespan=_lifespan,
)

# --- API Endpoints ---
@app.get("/health")
async def get_health_status():
    if await JupyterKernelManager.is_healthy():
        return {"status": "ok"}
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Kernel is not healthy")

@app.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_python_kernel():
    if not await JupyterKernelManager.reset_kernel():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset Python kernel.",
        )

@app.post("/execute", response_model=ExecuteResponse)
async def execute_python_code(request: ExecuteRequest) -> ExecuteResponse:
    result = await JupyterKernelManager.execute_code(request.code)

    if result.status == "ok":
        return ExecuteResponse(
            result_base64=result.value if result.type == 'image_png_base64' else None,
            result_text=result.value if result.type != 'image_png_base64' else None,
        )
    elif result.status == "timeout":
        l.warning("Code execution timed out. Triggering kernel auto-reset.")
        asyncio.create_task(JupyterKernelManager.reset_kernel())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Code execution timed out after {JupyterKernelManager.EXECUTION_TIMEOUT} seconds. Environment has been reset.",
        )
    else:  # status == "error"
        l.warning(f"Python execution failed. Type: {result.type}, Message: {result.value}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Python Execution Error: {result.value}",
        )

```

--- 

`worker\requirements.txt`

```
# --- Core Application ---
fastapi
uvicorn[standard]
loguru
httpx
pydantic
websockets
aiofiles

# --- Jupyter Kernel Backend ---
jupyter-kernel-gateway==3.0.1
ipykernel

# --- Scientific Computing Libraries ---
numpy
pandas
sympy
scipy
matplotlib
scikit-learn

```

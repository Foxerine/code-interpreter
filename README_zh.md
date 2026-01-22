# Code Interpreter API：一个有状态、高安全、高性能的 Python 沙箱

[English](README.md)

本项目是一个通过 API 驱动的、为实现**高安全性、有状态会话管理和强大性能**而设计的 Python 代码执行沙箱。它采用中心化的 **API 网关 (Gateway)** 和动态的 **工作实例池 (Worker Pool)** 架构，为每个用户提供一个完全隔离的、持久化的 Python 执行会话。

本项目的核心技术特性之一是其成功实现了 **“每个工作实例一个虚拟磁盘 (Virtual-Disk-per-Worker)”** 架构。这个先进的模型在运行时为每个工作容器动态地创建、格式化并通过 `losetup` 挂载一个专属的虚拟磁盘。该方法解决了在并发容器化环境中可靠地管理动态块设备的重大挑战，从而实现了卓越的 I/O 和文件系统隔离，这也是整个系统安全态势的基石。

每个工作实例都被一个多层安全模型沙箱化，该模型包括严格的资源限制、零信任网络策略和运行时权限降级。通过利用内部的 Jupyter Kernel，它能够在多次 API 调用之间保持完整的代码执行上下文（变量、导入、函数），确保了会话的连续性、安全性和高性能。

## 核心优势

| 特性 | 我们的实现 | 标准实现 (常见权衡) |
| :--- | :--- | :--- |
| **🚀 性能** | 预热的工作实例池确保了会话的即时分配。全异步设计 (FastAPI, httpx) 提供了高吞吐量 (约 32.8 RPS) 和低延迟。 | 为每个新会话按需启动容器/环境，导致高延迟。通常采用同步设计，在高负载下并发能力差。 |
| **🔒 安全性** | 多层零信任安全模型：无互联网访问 (`internal: true`)、工作实例间防火墙 (`iptables`)、网关不可访问、权限降级 (`root` to `sandbox`)。 | 基础的容器化通常允许出站互联网访问，缺少实例间防火墙（存在横向移动风险），且可能以过高权限运行代码。 |
| **🔄 状态保持** | 真正的会话持久化。每个用户被映射到一个专用的、拥有持久化 Jupyter Kernel 的工作实例，在所有 API 调用间保持完整的执行上下文。 | 无状态（每次调用都是新环境），或通过序列化等方式模拟状态（通常速度慢且不完整）。 |
| **🛠️ 可靠性** | “牲畜，而非宠物”的故障恢复模型。网关强制执行硬性超时并监控工作实例健康。任何失败、卡死或崩溃的实例都会被立即销毁和替换。 | 工作实例常被视为需要“修复”的状态化宠物，导致复杂的恢复逻辑，并增加了污染或不一致状态持续存在的风险。 |
| **💡 I/O 隔离**| **每个工作实例一个虚拟磁盘**。每个工作实例都拥有自己动态挂载的块设备，提供了与主机和其他工作实例之间真正的文件系统和 I/O 隔离。 | 通常依赖于共享的主机卷（存在交叉读写和安全漏洞的风险），或者完全没有持久化的隔离存储。 |

## 性能基准测试

为了验证其在真实场景下的性能和可伸缩性，我们在中端桌面平台上进行了压力测试。

### **测试配置：中端桌面平台 (Intel i5-14400, 16GB 内存)**

-   **测试场景**: 模拟 **25 个并发用户**，每个用户发送 100 次有状态的请求（并在每一步验证结果的正确性）。
-   **总请求数**: 2,500
-   **吞吐量 (RPS)**: **约 32.8 请求/秒**
-   **请求成功率**: **100%**
-   **状态验证成功率**: **100%**
-   **P95 延迟**: **496.50 毫秒**
-   **测试参数**: 本次基准测试在以下运行时配置下进行：
    -   最小空闲实例数 (`MinIdleWorkers`): 5
    -   最大实例总数 (`MaxTotalWorkers`): 30
    -   工作实例CPU限制 (`WorkerCPU`): 1.0 核
    -   工作实例内存限制 (`WorkerRAM_MB`): 1024 MB
    -   工作实例磁盘大小 (`WorkerDisk_MB`): 500 MB

### 测试结果图表

![测试结果概览饼图](images/1_test_summary_pie_chart.png)![延迟分布图](images/2_latency_distribution_chart.png)

## 架构解析

1.  **API 网关 (Gateway)**: 唯一的、需认证的入口。其 `WorkerPool` 是整个系统的大脑，管理工作实例的整个生命周期，包括为其动态创建虚拟磁盘的复杂过程。它扮演着可信的控制平面角色。
2.  **工作实例 (Worker)**: 一个不可信的、一次性的代码执行单元。它运行一个 `Supervisor`，以一个非 root 的 `sandbox` 用户身份管理两个子进程（FastAPI 服务, Jupyter Kernel）。在启动时，一个脚本会先配置好 `iptables` 防火墙（只允许来自网关的流量），挂载其专属虚拟磁盘，然后再降级权限。

![高层系统架构图](images/high_level_architecture_zh.png)![请求流程时序图](images/request_flow_sequence_zh.png)

## 文件传输架构

系统通过网关的**双挂载架构**提供安全、高性能的文件传输能力。这种设计允许网关直接访问每个工作实例的沙箱文件系统，无需通过不可信的工作容器路由流量。

### 工作原理

```
                                    ┌─────────────────────────────────────┐
                                    │         工作容器 (Worker)            │
   ┌──────────┐                     │  ┌───────────────────────────────┐  │
   │  客户端   │ ─── 预签名 URL ─────│──│ /sandbox (容器内绑定挂载)      │  │
   │  (OSS)   │                     │  │   └── user_data.xlsx          │  │
   └──────────┘                     │  │   └── output.png              │  │
        │                           │  └───────────────────────────────┘  │
        │                           └─────────────────────────────────────┘
        │                                              │
        │                                              │ (同一块设备)
        │                                              ▼
        │                           ┌─────────────────────────────────────┐
        │  HTTP PUT/GET             │        网关容器 (Gateway)            │
        └────────────────────────── │  ┌───────────────────────────────┐  │
                                    │  │ /worker_mounts/{worker_id}/   │  │
                                    │  │   └── user_data.xlsx          │  │
                                    │  │   └── output.png              │  │
                                    │  └───────────────────────────────┘  │
                                    │         (宿主机挂载点)               │
                                    └─────────────────────────────────────┘
```

1.  **上传**：网关从预签名 URL（如 OSS）下载文件，并通过自己的挂载点（`/worker_mounts/{worker_id}/`）直接写入工作实例的虚拟磁盘。
2.  **导出**：网关从其挂载点读取文件并上传到预签名 URL。数据永远不会经过不可信的工作进程。
3.  **删除**：网关直接从文件系统删除文件。

### 安全特性

| 特性 | 实现方式 | 防范的威胁 |
| :--- | :--- | :--- |
| **路径穿越防护** | 使用 `PurePosixPath.relative_to()` 验证所有路径都解析在 `/sandbox` 内。拒绝包含 `/` 或 `\` 的文件名。 | 目录穿越攻击（如 `../../../etc/passwd`） |
| **SSRF 防护** | 集成 `ssrf-protect` 库验证下载 URL。阻止请求私有 IP 范围（10.x、172.16.x、192.168.x、127.x）和内部主机名。 | 服务端请求伪造 (SSRF) |
| **重定向绕过防护** | 文件下载时禁用 HTTP 重定向（`allow_redirects=False`）。 | 通过恶意重定向到内部服务绕过 SSRF |
| **原子写入** | 上传使用临时文件 + 重命名模式，防止失败时产生部分/损坏文件。 | 传输中断导致的数据损坏 |
| **文件大小限制** | 强制执行单文件大小限制（默认 100MB），使用流式验证。超出限制时立即中止传输。 | 磁盘耗尽攻击 |
| **符号链接攻击防护** | 使用 `nosymfollow` 选项（Linux 5.10+）挂载虚拟磁盘。挂载前验证挂载点不是符号链接。 | 基于符号链接的沙箱逃逸 |
| **并发控制** | 使用信号量限制并发文件操作，防止资源耗尽。 | 通过并发传输洪水进行的 DoS 攻击 |

## 快速开始

### 1. 前提条件

-   [Docker](https://www.docker.com/) 和 [Docker Compose](https://docs.docker.com/compose/) 已正确安装并正在运行。
-   一个 HTTP 客户端 (如 cURL, Postman, 或 Python 的 `httpx` 库)。

### 2. 启动服务

项目提供了便捷的脚本来启动环境。您可以通过命令行参数自定义资源分配和实例池大小。

-   **Linux / macOS 用户:** `sh start.sh [参数]`
-   **Windows 用户 (PowerShell):** `.\start.ps1 [参数]`

服务启动后，网关将在 `http://127.0.0.1:3874` 上监听请求。

#### 自定义环境配置

您可以在启动脚本后附加以下参数来配置系统的行为。

| 参数 | Shell (`.sh`) | PowerShell (`.ps1`) | 默认值 | 描述 |
| :--- | :--- | :--- | :--- | :--- |
| 最小空闲实例 | `--min-idle-workers` | `-MinIdleWorkers` | `5` | 池中保持的最小空闲、预热的工作实例数量。 |
| 最大实例总数 | `--max-total-workers`| `-MaxTotalWorkers` | `50` | 系统允许创建的并发工作容器的最大总数。 |
| Worker CPU | `--worker-cpu` | `-WorkerCPU` | `1.0` | 分配给每个工作容器的 CPU 核心数 (例如 `1.5` 代表一个半核心)。 |
| Worker 内存 | `--worker-ram-mb` | `-WorkerRAM_MB` | `1024` | 分配给每个工作容器的内存大小 (单位: MB)。 |
| Worker 磁盘 | `--worker-disk-mb` | `-WorkerDisk_MB` | `500` | 为每个工作实例的沙箱文件系统创建的虚拟磁盘大小 (单位: MB)。 |

**示例 (Linux/macOS):**
```bash
# 启动一个拥有更大实例池和更强性能实例的系统
sh start.sh --min-idle-workers 10 --worker-cpu 2.0 --worker-ram-mb 2048
```

**示例 (Windows PowerShell):**
```powershell
# 启动一个适用于低资源环境的轻量级配置
.\start.ps1 -MinIdleWorkers 2 -MaxTotalWorkers 10 -WorkerCPU 0.5 -WorkerRAM_MB 512
```

### 3. 获取认证令牌

从正在运行的网关容器中获取自动生成的令牌：
```bash
docker exec code-interpreter_gateway cat /gateway/auth_token.txt
```
要进行快速的 UI 测试，可以在浏览器中打开项目内的 `test.html` 文件，粘贴令牌，然后点击“New Session”。

### 4. 停止服务

-   **Linux / macOS 用户:** `sh stop.sh`
-   **Windows 用户 (PowerShell):** `.\stop.ps1`

## API 接口文档

所有端点都以 `/api/v1` 为前缀。所有请求都需要 `X-Auth-Token: <你的令牌>` 请求头。

### 1. 执行代码 `POST /api/v1/execute?user_uuid={uuid}`
在用户的有状态会话中执行 Python 代码。
-   **查询参数**: `user_uuid` (必需) - 用户会话的 UUID 标识符
-   **请求体**: `{ "code": "string" }`
-   **成功响应 (200 OK)**: `{ "worker_id": "string", "result_text": "string | null", "result_base64": "string | null" }`
-   **超时/崩溃响应 (503/504)**: 表示发生了致命错误。环境已被销毁和回收。

### 2. 释放会话 `POST /api/v1/release?user_uuid={uuid}`
主动终止一个用户的会话并销毁其工作实例。
-   **查询参数**: `user_uuid` (必需) - 用户会话的 UUID 标识符
-   **成功响应 (204 No Content)**

### 3. 获取系统状态 `GET /api/v1/status` (管理接口)
返回工作池状态的摘要信息，用于监控。
-   **成功响应 (200 OK)**:
    ```json
    {
        "total_workers": 10,
        "busy_workers": 3,
        "is_initializing": false
    }
    ```

### 4. 批量上传文件到沙箱 `POST /api/v1/files?user_uuid={uuid}`
从预签名 URL 批量下载文件并保存到用户的工作实例沙箱中。支持并发处理。
-   **查询参数**: `user_uuid` (必需) - 用户会话的 UUID 标识符
-   **限制**: 每次请求最多 100 个文件，单个文件最大 100MB
-   **请求体**:
    ```json
    {
        "files": [
            {"download_url": "https://...", "path": "/sandbox/", "name": "data.xlsx"},
            {"download_url": "https://...", "path": "/sandbox/", "name": "image.png"}
        ]
    }
    ```
-   **成功响应 (201 Created)**:
    ```json
    {
        "success": true,
        "results": [
            {"full_path": "/sandbox/data.xlsx", "size": 12345},
            {"full_path": "/sandbox/image.png", "size": 67890}
        ]
    }
    ```

### 5. 批量从沙箱导出文件 `POST /api/v1/files/export?user_uuid={uuid}`
从沙箱读取文件并通过预签名 URL 上传到 OSS。支持并发处理。
-   **查询参数**: `user_uuid` (必需) - 用户会话的 UUID 标识符
-   **限制**: 每次请求最多 100 个文件
-   **请求体**:
    ```json
    {
        "files": [
            {"path": "/sandbox/", "name": "result.xlsx", "upload_url": "https://..."},
            {"path": "/sandbox/", "name": "chart.png", "upload_url": "https://..."}
        ]
    }
    ```
-   **成功响应 (200 OK)**:
    ```json
    {
        "success": true,
        "results": [
            {"path": "/sandbox/", "name": "result.xlsx", "size": 8192},
            {"path": "/sandbox/", "name": "chart.png", "size": 54321}
        ]
    }
    ```

### 6. 批量删除沙箱文件 `DELETE /api/v1/files?user_uuid={uuid}`
批量删除用户工作实例沙箱中的文件。
-   **查询参数**: `user_uuid` (必需) - 用户会话的 UUID 标识符
-   **限制**: 每次请求最多 100 个文件
-   **请求体**:
    ```json
    {
        "files": [
            {"path": "/sandbox/", "name": "temp.xlsx"},
            {"path": "/sandbox/", "name": "old.png"}
        ]
    }
    ```
-   **成功响应 (204 No Content)**

## 使用示例 (Python)

```python
import httpx
import asyncio
import uuid
import base64
import subprocess

GATEWAY_URL = "http://127.0.0.1:3874"
USER_ID = str(uuid.uuid4())

def get_auth_token():
    try:
        return subprocess.check_output(
            ["docker", "exec", "code-interpreter_gateway", "cat", "/gateway/auth_token.txt"],
            text=True
        ).strip()
    except Exception:
        print("❌ 无法获取 Auth Token。服务是否已启动？")
        return None

async def execute_code(client: httpx.AsyncClient, code: str):
    print(f"\n--- 正在执行 ---\n{code.strip()}")
    try:
        response = await client.post(
            f"{GATEWAY_URL}/api/v1/execute",
            params={"user_uuid": USER_ID},
            json={"code": code},
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
        if data.get("result_text"):
            print(">>> 文本结果:\n" + data["result_text"])
        if data.get("result_base64"):
            print(">>> 成功生成图像！(已保存为 output.png)")
            with open("output.png", "wb") as f:
                f.write(base64.b64decode(data["result_base64"]))
    except httpx.HTTPStatusError as e:
        print(f"执行失败: {e.response.status_code} - {e.response.text}")

async def main():
    token = get_auth_token()
    if not token: return
    
    headers = {"X-Auth-Token": token}
    async with httpx.AsyncClient(headers=headers) as client:
        # 步骤 1: 定义一个变量
        await execute_code(client, "a = 100")
        # 步骤 2: 使用上一步的变量 (状态被保持)
        await execute_code(client, "print(f'变量 a 的值是 {a}')")

if __name__ == "__main__":
    asyncio.run(main())
```
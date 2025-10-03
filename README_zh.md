# Code Interpreter API：一个有状态、高安全、高性能的 Python 沙箱

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

1.  **API 网关 (Gateway)**: 唯一的、需认证的入口。其 `WorkerManager` 是整个系统的大脑，管理工作实例的整个生命周期，包括为其动态创建虚拟磁盘的复杂过程。它扮演着可信的控制平面角色。
2.  **工作实例 (Worker)**: 一个不可信的、一次性的代码执行单元。它运行一个 `Supervisor`，以一个非 root 的 `sandbox` 用户身份管理两个子进程（FastAPI 服务, Jupyter Kernel）。在启动时，一个脚本会先配置好 `iptables` 防火墙（只允许来自网关的流量），挂载其专属虚拟磁盘，然后再降级权限。

![高层系统架构图](images/high_level_architecture_zh.png)![请求流程时序图](images/request_flow_sequence_zh.png)

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

所有请求都需要 `X-Auth-Token: <你的令牌>` 请求头。

### 1. 执行代码 `POST /execute`
在用户的有状态会话中执行 Python 代码。
-   **请求体**: `{ "user_uuid": "string", "code": "string" }`
-   **成功响应 (200 OK)**: `{ "result_text": "string | null", "result_base64": "string | null" }`
-   **超时/崩溃响应 (503/504)**: 表示发生了致命错误。环境已被销毁和回收。

### 2. 释放会话 `POST /release`
主动终止一个用户的会话并销毁其工作实例。
-   **请求体**: `{ "user_uuid": "string" }`
-   **成功响应 (200 OK)**: `{ "status": "ok", "detail": "..." }`

### 3. 获取系统状态 `GET /status` (管理接口)
返回工作池状态的摘要信息，用于监控。

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
    payload = {"user_uuid": USER_ID, "code": code}
    try:
        response = await client.post(f"{GATEWAY_URL}/execute", json=payload, timeout=30.0)
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
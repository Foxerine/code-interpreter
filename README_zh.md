# Code Interpreter：一个有状态、高性能、高安全性的 Python 代码沙箱 API

本项目是一个通过 API 驱动的、强大的 Python 代码执行沙箱。它采用中心化的 **API 网关 (Gateway)** 和动态的 **工作实例池 (Worker Pool)** 架构，为每个用户提供一个完全隔离的、有状态的、持久化的 Python 执行会话。

每个工作实例都在一个独立的 Docker 容器中运行，并通过一个包含严格资源限制、网络隔离和运行时权限降级的多层安全模型进行沙箱化。通过利用内部的 Jupyter Kernel，它能够在多次 API 调用之间保持完整的代码执行上下文（变量、导入、函数等），从而确保了极致的安全性、对话的连续性和卓越的性能。

## 核心特性

-   **有状态会话**: 每个用户 (通过 `user_uuid` 标识) 在会话期间会被唯一地映射到一个专用的工作实例。这保证了变量、函数定义和导入的库在连续的 API 请求之间得以保持，从而支持复杂的多步计算任务。

-   **极致隔离与多层安全**:
    -   **中心化访问控制**: 所有请求都必须通过 API 网关，网关负责统一的令牌认证，工作实例绝不直接暴露。
    -   **零信任网络策略**:
        *   **无互联网访问**: 工作容器运行在一个 `internal: true` 的网络中，完全阻断任何对互联网的出站流量。
        *   **无法访问网关**: 网关的 API 服务绑定在一个特定的网络接口上，该接口从工作网络的角度是无法访问的，从而防止工作实例对控制平面发起攻击。
        *   **工作实例间隔离**: 每个工作实例在启动时（以 `root` 权限）会配置一个不可变的 `iptables` 防火墙，该防火墙**拒绝除网关之外的所有入站流量**。这彻底杜绝了容器之间的横向移动或互相干扰的可能性。
    -   **权限降级**: 在设置完防火墙后，每个工作实例会在执行任何用户代码之前，将其权限永久降级为一个无特权的 `sandbox` 用户。这可以防止用户篡改容器的系统级配置或防火墙规则。

-   **高性能与高并发**:
    -   **预热工作池**: 系统维护一个由空闲的、随时可用的工作实例组成的池。当新用户发起请求时，系统会立即从池中分配一个实例，从而消除了环境启动的延迟。
    -   **全异步设计**: 网关和工作实例均基于 FastAPI 和异步库构建，能够高效地处理大量并发请求。

-   **健壮的“牲畜模式”故障恢复**:
    -   **中心化健康与超时控制**: 网关是管理工作实例健康状况的唯一权威。它对所有代码执行请求强制实施硬性超时。
    -   **立即销毁并替换**: 如果工作实例的代码执行超时，或因任何原因崩溃，网关会立即将其视为“已污染”。它会被立即销毁并从池中移除，同时一个新的、干净的实例会被创建以作补充。这种“牲畜，而非宠物”的理念确保了最高的系统稳定性和安全性，因为它从不尝试“修复”一个可能已被破坏的环境。

## 性能基准测试

为了验证系统的性能和可伸缩性，我们在不同的硬件配置上进行了压力测试。

---

### **测试一：高端桌面平台 (AMD 9950X, 128GB 内存)**

-   **测试场景**: 模拟 **30 个并发用户**，每个用户发送 100 次有状态的请求。
-   **总请求数**: 3,000
-   **吞吐量 (RPS)**: **约 37.7 请求/秒**
-   **请求成功率**: **99.9%**
-   **P95 延迟**: **262.92 毫秒**

---

### **测试二：中端桌面平台 (Intel i5-14400, 16GB 内存)**

-   **测试场景**: 模拟 **25 个并发用户**，每个用户发送 100 次有状态的请求。
-   **总请求数**: 2,500
-   **吞吐量 (RPS)**: **约 35.9 请求/秒**
-   **请求成功率**: **100%**
-   **P95 延迟**: **404.15 毫秒**

---

### 测试结果图表 (源自高端平台测试)

![测试结果概览饼图](images/1_test_summary_pie_chart.png)
![延迟分布图](images/2_latency_distribution_chart.png)

## 架构解析

1.  **API 网关 (Gateway)**: 唯一的、需认证的入口。其 `WorkerManager` 管理工作实例的整个生命周期。它扮演着可信的控制平面角色。
2.  **工作实例 (Worker)**: 一个不可信的、一次性的代码执行单元。它运行一个 `Supervisor`，该进程以一个非 root 的 `sandbox` 用户身份管理两个子进程（FastAPI 服务, Jupyter Kernel）。在启动时，一个脚本会先配置好 `iptables` 防火墙（只允许来自网关的流量），然后再降级权限。

![高层系统架构图](images/high_level_architecture_zh.png)
![请求流程时序图](images/request_flow_sequence_zh.png)

## 快速开始

### 1. 前提条件

-   [Docker](https://www.docker.com/) 和 [Docker Compose](https://docs.docker.com/compose/) 已正确安装并正在运行。
-   一个 HTTP 客户端 (如 cURL, Postman, 或 Python 的 `httpx` 库)。

### 2. 启动服务

项目提供了便捷的脚本。请**不要**直接运行 `docker-compose up`。

-   **Linux / macOS 用户:** `sh start.sh`
-   **Windows 用户 (PowerShell):** `.\start.ps1`

服务启动后，网关将在 `http://127.0.0.1:3874` 上监听请求。

### 3. 获取认证令牌

从正在运行的网关容器中获取自动生成的令牌：
```bash
docker exec code-interpreter_gateway cat /gateway/auth_token.txt
```
你可以使用项目中的 `test.html` 文件进行快速的 UI 测试。

### 4. 停止服务

-   **Linux / macOS 用户:** `sh stop.sh`
-   **Windows 用户 (PowerShell):** `.\stop.ps1`

## API 接口文档

所有请求都需要 `X-Auth-Token: <你的令牌>` 请求头。

### 1. 执行代码 `POST /execute`
在用户的有状态会话中执行 Python 代码。
-   **请求体**: `{ "user_uuid": "string", "code": "string" }`
-   **成功响应 (200 OK)**: `{ "result_text": "string | null", "result_base64": "string | null" }`
-   **超时响应 (504 Gateway Timeout)**: 表示代码运行时间过长，环境已被回收。

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
        await execute_code(client, "a = 100")
        await execute_code(client, "print(f'变量 a 的值是 {a}')")

if __name__ == "__main__":
    asyncio.run(main())
```

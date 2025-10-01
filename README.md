# Code Interpreter: A Stateful, High-Performance, and Secure Python Sandbox API

This project delivers a robust, API-driven Python code execution sandbox. It features a centralized **API Gateway** and a dynamic **Worker Pool** architecture, providing each user with a completely isolated, stateful, and persistent Python session.

Each worker instance operates within its own Docker container, sandboxed with a multi-layered security model that includes strict resource limits, network isolation, and runtime privilege reduction. By leveraging an internal Jupyter Kernel, it maintains the complete code execution context (variables, imports, functions) across multiple API calls, ensuring ultimate security, session continuity, and high performance.

## Core Features

-   **Stateful Sessions**: Each user (identified by `user_uuid`) is uniquely mapped to a dedicated worker instance. This guarantees that variables, function definitions, and imported libraries are persisted across consecutive API requests, enabling complex, multi-step computations.

-   **Ultimate Isolation & Multi-Layered Security**:
    -   **Centralized Access Control**: All requests are routed through the API Gateway, which enforces unified token authentication. Worker instances are never directly exposed.
    -   **Zero Trust Network Policy**:
        *   **No Internet Access**: Worker containers run in a network with `internal: true`, completely blocking any outbound traffic to the internet.
        *   **No Gateway Access**: The Gateway's API server is bound to a specific network interface that is unreachable from the worker's network, preventing workers from initiating attacks against the control plane.
        *   **Worker-to-Worker Isolation**: At startup, each worker (as `root`) configures an immutable `iptables` firewall that **drops all incoming traffic except from the Gateway**. This prevents any possibility of lateral movement or interference between containers, even if a user gains control within their own sandbox.
    -   **Privilege Reduction**: After setting up its firewall, each worker permanently drops privileges to an unprivileged `sandbox` user before executing any code. This prevents users from tampering with the container's system-level configurations or firewall rules.

-   **High Performance & Concurrency**:
    -   **Pre-warmed Worker Pool**: The system maintains a pool of idle, ready-to-use worker instances. When a new user makes a request, an instance is instantly allocated, eliminating environment startup latency.
    -   **Fully Asynchronous Design**: Built entirely with FastAPI and asynchronous libraries, both the Gateway and Workers can handle a high volume of concurrent requests efficiently.

-   **Robust "Cattle, not Pets" Recovery Model**:
    -   **Centralized Health & Timeout Control**: The Gateway is the sole authority for managing worker health. It imposes a hard timeout on all code execution requests.
    -   **Instant Kill-and-Replace**: If a worker's code execution times out, or if the worker crashes for any reason, the Gateway immediately considers it "contaminated." It is instantly destroyed and removed from the pool, and a fresh, clean instance is created to take its place. This "cattle, not pets" philosophy ensures maximum system stability and security, as no attempt is made to "heal" a potentially compromised environment.

## Performance Benchmarks

The system was stress-tested on different hardware configurations to validate its performance and scalability.

---

### **Test 1: High-End Desktop (AMD 9950X, 128GB RAM)**

-   **Test Scenario**: **30 concurrent users**, each sending 100 stateful requests.
-   **Total Requests**: 3,000
-   **Throughput (RPS)**: **~37.7 req/s**
-   **Request Success Rate**: **99.9%**
-   **P95 Latency**: **262.92 ms**

---

### **Test 2: Mid-Range Desktop (Intel i5-14400, 16GB RAM)**

-   **Test Scenario**: **25 concurrent users**, each sending 100 stateful requests.
-   **Total Requests**: 2,500
-   **Throughput (RPS)**: **~35.9 req/s**
-   **Request Success Rate**: **100%**
-   **P95 Latency**: **404.15 ms**

---

### Result Charts (from High-End Test)

![Test Summary Pie Chart](images/1_test_summary_pie_chart.png)
![Latency Distribution Chart](images/2_latency_distribution_chart.png)

## Architecture Overview

1.  **API Gateway**: The single, authenticated entry point. Its `WorkerManager` manages the entire lifecycle of worker instances. It acts as the trusted control plane.
2.  **Worker Instance**: An untrusted, disposable code execution unit. It runs a `Supervisor` that manages two processes (FastAPI service, Jupyter Kernel) as a non-root `sandbox` user. At startup, a script configures an `iptables` firewall to only accept traffic from the Gateway before dropping root privileges.

![High-Level System Architecture](images/high_level_architecture_en.png)
![Request Flow Sequence Diagram](images/request_flow_sequence_en.png)

## Quick Start

### 1. Prerequisites

-   [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) installed and running.
-   An HTTP client (e.g., cURL, Postman, or Python's `httpx`).

### 2. Start the Service

Convenience scripts are provided. **Do not** run `docker-compose up` directly.

-   **Linux / macOS:** `sh start.sh`
-   **Windows (PowerShell):** `.\start.ps1`

The gateway will listen on `http://127.0.0.1:3874`.

### 3. Get the Auth Token

Retrieve the auto-generated token from the running gateway container:
```bash
docker exec code-interpreter_gateway cat /gateway/auth_token.txt
```
Use the included `test.html` for a quick UI test.

### 4. Stop the Service

-   **Linux / macOS:** `sh stop.sh`
-   **Windows (PowerShell):** `.\stop.ps1`

## API Documentation

All requests require the `X-Auth-Token: <your-token>` header.

### 1. Execute Code `POST /execute`
Executes Python code within a user's stateful session.
-   **Request Body**: `{ "user_uuid": "string", "code": "string" }`
-   **Success Response (200 OK)**: `{ "result_text": "string | null", "result_base64": "string | null" }`
-   **Timeout Response (504 Gateway Timeout)**: Indicates the code ran too long and the environment was recycled.

### 2. Release Session `POST /release`
Proactively terminates a user's session and destroys its worker.
-   **Request Body**: `{ "user_uuid": "string" }`
-   **Success Response (200 OK)**: `{ "status": "ok", "detail": "..." }`

### 3. Get System Status `GET /status` (Admin)
Returns a summary of the worker pool's status for monitoring.

## Usage Example (Python)

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
        print("❌ Could not fetch Auth Token. Is the service running?")
        return None

async def execute_code(client: httpx.AsyncClient, code: str):
    print(f"\n--- Executing ---\n{code.strip()}")
    payload = {"user_uuid": USER_ID, "code": code}
    try:
        response = await client.post(f"{GATEWAY_URL}/execute", json=payload, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        if data.get("result_text"):
            print(">>> Text Result:\n" + data["result_text"])
        if data.get("result_base64"):
            print(">>> Image generated! (output.png saved)")
            with open("output.png", "wb") as f:
                f.write(base64.b64decode(data["result_base64"]))
    except httpx.HTTPStatusError as e:
        print(f"Execution failed: {e.response.status_code} - {e.response.text}")

async def main():
    token = get_auth_token()
    if not token: return
    
    headers = {"X-Auth-Token": token}
    async with httpx.AsyncClient(headers=headers) as client:
        await execute_code(client, "a = 100")
        await execute_code(client, "print(f'The value of a is {a}')")

if __name__ == "__main__":
    asyncio.run(main())
```

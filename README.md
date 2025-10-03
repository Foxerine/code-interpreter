# Code Interpreter API: A Stateful, Secure, and High-Performance Python Sandbox

This project provides a robust, API-driven Python code execution sandbox, engineered for high security, stateful session management, and strong performance. It utilizes a centralized **API Gateway** and a dynamic **Worker Pool** architecture, providing each user with a completely isolated and persistent Python session.

A key technical feature of this project is its successful implementation of a **"Virtual-Disk-per-Worker"** architecture. This advanced model dynamically creates, formats, and mounts a dedicated virtual disk (`.img` file via `losetup`) for each worker container at runtime. This approach addresses the significant challenge of reliably managing dynamic block devices in a concurrent containerized environment, enabling superior I/O and filesystem isolation that is fundamental to the system's security posture.

Each worker is sandboxed within a multi-layered security model that includes strict resource limits, a zero-trust network policy, and runtime privilege reduction. By leveraging an internal Jupyter Kernel, it maintains the complete code execution context (variables, imports, functions) across multiple API calls, ensuring session continuity, security, and high performance.

## Key Advantages

| Feature | Our Approach | Standard Implementations (Common Trade-offs) |
| :--- | :--- | :--- |
| **🚀 Performance** | A pre-warmed pool of idle workers ensures instant session allocation. The fully asynchronous design (FastAPI, httpx) delivers high throughput (~32.8 RPS) and low latency. | High latency due to on-demand container/environment startup for each new session. Often synchronous, leading to poor concurrency under load. |
| **🔒 Security** | A multi-layered, zero-trust security model: no internet access (`internal: true`), inter-worker firewalls (`iptables`), gateway inaccessibility, and privilege drop (`root` to `sandbox`). | Basic containerization often allows outbound internet access, lacks inter-worker firewalls (risk of lateral movement), and may run code with excessive privileges. |
| **🔄 Statefulness** | True session persistence. Each user is mapped to a dedicated worker with a persistent Jupyter Kernel, maintaining the full execution context across all API calls. | Stateless (each call is a new environment) or emulated statefulness (e.g., saving/loading state via serialization), which is often slow and incomplete. |
| **🛠️ Reliability** | A "Cattle, not Pets" fault tolerance model. The gateway enforces hard timeouts and monitors worker health. Any failed, hung, or crashed worker is instantly destroyed and replaced. | Workers are often treated as stateful "pets" that require complex recovery logic, increasing the risk of contaminated or inconsistent states persisting. |
| **💡 I/O Isolation** | **Virtual-Disk-per-Worker Architecture**. Each worker gets its own dynamically mounted block device, providing true filesystem and I/O isolation from the host and other workers. | Often relies on shared host volumes (risk of cross-talk and security breaches) or has no persistent, isolated storage at all. |

## Performance Benchmarks

Stress-tested on a mid-range desktop to validate its performance and scalability under realistic conditions.

### **Test Configuration: Mid-Range Desktop (Intel i5-14400, 16GB RAM)**

-   **Test Scenario**: **25 concurrent users**, each sending 100 stateful requests (with result verification at each step).
-   **Total Requests**: 2,500
-   **Throughput (RPS)**: **~32.8 req/s**
-   **Request Success Rate**: **100%**
-   **State Verification Success Rate**: **100%**
-   **P95 Latency**: **496.50 ms**

### Result Charts

![Test Summary Pie Chart](images/1_test_summary_pie_chart.png)![Latency Distribution Chart](images/2_latency_distribution_chart.png)

## Architecture Overview

1.  **API Gateway**: The single, authenticated entry point. Its `WorkerManager` manages the entire lifecycle of worker instances, including the dynamic creation of their virtual disks. It acts as the trusted control plane.
2.  **Worker Instance**: An untrusted, disposable code execution unit. It runs a `Supervisor` that manages two processes (FastAPI service, Jupyter Kernel) as a non-root `sandbox` user. At startup, a script configures an `iptables` firewall to only accept traffic from the Gateway before dropping root privileges and mounting its dedicated virtual disk.

![High-Level System Architecture](images/high_level_architecture_en.png)![Request Flow Sequence Diagram](images/request_flow_sequence_en.png)

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
For a quick UI test, open the included `test.html` file in your browser, paste the token, and click "New Session".

### 4. Stop the Service

-   **Linux / macOS:** `sh stop.sh`
-   **Windows (PowerShell):** `.\stop.ps1`

## API Documentation

All requests require the `X-Auth-Token: <your-token>` header.

### 1. Execute Code `POST /execute`
Executes Python code within a user's stateful session.
-   **Request Body**: `{ "user_uuid": "string", "code": "string" }`
-   **Success Response (200 OK)**: `{ "result_text": "string | null", "result_base64": "string | null" }`
-   **Timeout/Crash Response (503/504)**: Indicates a fatal error. The environment has been destroyed and recycled.

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
        # Step 1: Define a variable
        await execute_code(client, "a = 100")
        # Step 2: Use the variable from the previous step (state is maintained)
        await execute_code(client, "print(f'The value of a is {a}')")

if __name__ == "__main__":
    asyncio.run(main())

import httpx
import asyncio
import uuid
import base64
import os
import subprocess

# --- 配置 ---
GATEWAY_URL = "http://127.0.0.1:3874"
AUTH_TOKEN = "" # 将在此处填充

# 为这个会话生成一个唯一的用户 ID
USER_ID = str(uuid.uuid4())

HEADERS = {}

def get_auth_token():
    """通过 docker exec 命令从容器中获取令牌"""
    try:
        token = subprocess.check_output(
            ["docker", "exec", "code-interpreter_gateway", "cat", "/gateway/auth_token.txt"],
            text=True
        ).strip()
        return token
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ 无法自动获取 Auth Token。请确保服务已通过 start.sh/start.ps1 启动。")
        print("   请手动运行 'docker exec code-interpreter_gateway cat /gateway/auth_token.txt' 并将令牌粘贴到 AUTH_TOKEN 变量中。")
        return None

async def execute_code(client: httpx.AsyncClient, session_id: str, code: str):
    """一个辅助函数，用于发送执行请求并打印结果。"""
    print(f"\n--- 正在执行代码 ---\n{code.strip()}")
    payload = {"user_uuid": session_id, "code": code}

    try:
        response = await client.post(f"{GATEWAY_URL}/execute", json=payload, headers=HEADERS, timeout=30.0)
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
    global AUTH_TOKEN, HEADERS
    AUTH_TOKEN = get_auth_token()
    if not AUTH_TOKEN:
        return

    HEADERS = {"X-Auth-Token": AUTH_TOKEN}
    print(f"✅ 成功获取令牌: ...{AUTH_TOKEN[-6:]}")

    async with httpx.AsyncClient() as client:
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
    asyncio.run(main())

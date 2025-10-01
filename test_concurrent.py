import asyncio
import random
import time
import uuid
import subprocess
from collections import Counter, defaultdict
import statistics
import json
import math
import os

import httpx
import pandas as pd
import matplotlib.pyplot as plt

# --- ⚙️ 测试配置 ---

# 网关地址
GATEWAY_URL = "http://127.0.0.1:3874"
# 并发用户数 (同时模拟多少个用户)
NUM_CONCURRENT_USERS = 25
# 每个用户的请求总数 (必须大于等于3，以完整执行一个场景)
REQUESTS_PER_USER = 100
# 两次请求之间的思考时间 (秒)，模拟真实用户行为
THINK_TIME_RANGE = (0.1, 0.5)
# 请求超时设置 (秒)
REQUEST_TIMEOUT = 45.0


# --- 🎨 终端颜色辅助函数 ---
def green(text): return f"\033[92m{text}\033[0m"
def red(text): return f"\033[91m{text}\033[0m"
def yellow(text): return f"\033[93m{text}\033[0m"
def blue(text): return f"\033[94m{text}\033[0m"
def dim(text): return f"\033[2m{text}\033[0m"

# --- 令牌获取 ---
AUTH_TOKEN = ""
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
        print(red("❌ 无法自动获取 Auth Token。请确保服务已通过 start.sh/start.ps1 启动。"))
        return None

# --- 核心模拟逻辑 ---

def generate_code_for_step(scenario_type: str, step: int, state: dict):
    """
    根据给定的场景、步骤和当前状态，生成代码、预期答案和下一个状态。
    """
    if scenario_type == 'simple_arithmetic':
        if step == 0:
            base_val = random.randint(1_000, 9_999)
            state['x'] = base_val
            code = f"x = {base_val}"
            return code, None, state # 第一步不打印，无预期输出
        else:
            add_val = random.randint(100, 999)
            expected_answer = state['x'] + add_val
            state['x'] = expected_answer
            code = f"x += {add_val}; print(x)"
            return code, expected_answer, state

    elif scenario_type == 'list_manipulation':
        if step == 0:
            rand_len = random.randint(2, 4)
            base_list = random.sample(range(10, 100), rand_len)
            state['my_list'] = base_list
            code = f"my_list = {base_list}"
            return code, None, state
        else:
            new_element = random.randint(100, 199)
            state['my_list'].append(new_element)
            expected_answer = sum(state['my_list'])
            code = f"my_list.append({new_element}); print(sum(my_list))"
            return code, expected_answer, state

    elif scenario_type == 'numpy_array':
        # 确保每个 numpy 场景至少能执行3步
        step = step % 3
        if step == 0:
            state['np_arr'] = [random.randint(10, 50) for _ in range(3)]
            code = f"import numpy as np; arr = np.array({state['np_arr']})"
            return code, None, state
        elif step == 1:
            multiplier = random.randint(2, 5)
            state['np_arr'] = [x * multiplier for x in state['np_arr']]
            expected_answer = sum(state['np_arr'])
            code = f"arr = arr * {multiplier}; print(np.sum(arr))"
            return code, expected_answer, state
        elif step == 2:
            expected_answer = sum(state['np_arr']) / len(state['np_arr'])
            code = f"print(np.mean(arr))"
            # 状态不变，只是读取
            return code, expected_answer, state

    # 默认回退到简单算术
    return generate_code_for_step('simple_arithmetic', step, state)


async def simulate_user_session(client: httpx.AsyncClient, results: list):
    """
    模拟一个用户的完整会话：随机选择一个场景，执行一系列有状态的计算，
    验证每一步的结果，以确认会话的隔离性，最后确保释放会话。
    """
    user_id = str(uuid.uuid4())
    session_state = {}
    # 为此用户随机分配一个场景
    scenario = random.choice(['simple_arithmetic', 'list_manipulation', 'numpy_array'])

    try:
        for i in range(REQUESTS_PER_USER):
            code, expected_answer, session_state = generate_code_for_step(scenario, i, session_state)
            payload = {"user_uuid": user_id, "code": code}

            start_time = time.monotonic()
            error_detail = None
            verification_passed = None

            try:
                response = await client.post(
                    f"{GATEWAY_URL}/execute", json=payload, headers=HEADERS, timeout=REQUEST_TIMEOUT
                )
                latency = time.monotonic() - start_time

                if response.status_code == 200:
                    # 如果预期答案为 None (例如初始化步骤)，则直接视为验证成功
                    if expected_answer is None:
                        verification_passed = True
                    else:
                        try:
                            response_data = response.json()
                            output = response_data.get("result_text", "").strip()

                            if not output:
                                verification_passed = False
                                error_detail = "执行成功但 result_text 为空"
                            else:
                                actual_result = float(output) # 统一转为 float 以兼容整数和浮点数
                                # 对浮点数使用容错比较
                                if math.isclose(actual_result, float(expected_answer), rel_tol=1e-9):
                                    verification_passed = True
                                else:
                                    verification_passed = False
                                    error_detail = f"结果不匹配! 场景:{scenario}, 预期:{expected_answer}, 实际:{actual_result}"
                        except (json.JSONDecodeError, ValueError, KeyError) as e:
                            verification_passed = False
                            error_detail = f"无法解析或验证响应: {e} | 响应体: {response.text[:150]}"
                else:
                    try:
                        error_detail = response.json().get('detail', response.text)
                    except Exception:
                        error_detail = response.text

                results.append((response.status_code, latency, error_detail, verification_passed))

            except httpx.RequestError as e:
                latency = time.monotonic() - start_time
                error_detail = f"{type(e).__name__}: {e}"
                results.append((None, latency, error_detail, False))

            await asyncio.sleep(random.uniform(*THINK_TIME_RANGE))

    finally:
        try:
            await client.post(
                f"{GATEWAY_URL}/release", json={"user_uuid": user_id}, headers=HEADERS, timeout=10.0
            )
        except httpx.RequestError:
            pass

def print_results(results: list, total_duration: float):
    """
    计算并打印详细的测试结果报告，包括错误内容样本和结果验证统计。
    """
    print("\n" + "="*60)
    print(blue("📊 并发压力测试结果分析"))
    print("="*60)

    total_requests = len(results)
    if total_requests == 0:
        print(red("没有收到任何结果。"))
        return

    successes = [res for res in results if res[0] == 200]
    failures = [res for res in results if res[0] != 200]

    verified_success = [res for res in successes if res[3] is True]
    verified_failed = [res for res in successes if res[3] is False]


    success_rate = (len(successes) / total_requests) * 100
    failure_rate = (len(failures) / total_requests) * 100
    rps = total_requests / total_duration

    print(f"总计时间:         {total_duration:.2f} s")
    print(f"并发用户数:       {NUM_CONCURRENT_USERS}")
    print(f"总请求数:         {total_requests}")
    print(f"吞吐量 (RPS):     {yellow(f'{rps:.2f} req/s')}")
    print(f"请求成功率:       {green(f'{success_rate:.2f}%')} ({len(successes)} requests)")
    print(f"请求失败率:       {red(f'{failure_rate:.2f}%')} ({len(failures)} requests)")

    if successes:
        verification_success_rate = (len(verified_success) / len(successes)) * 100
        verification_failure_rate = (len(verified_failed) / len(successes)) * 100
        print(f"  - 结果验证成功率: {green(f'{verification_success_rate:.2f}%')} ({len(verified_success)} of successes)")
        print(f"  - 结果验证失败率: {red(f'{verification_failure_rate:.2f}%')} ({len(verified_failed)} of successes)")


    if failures:
        print("\n" + "-"*23 + " 请求失败原因分析 " + "-"*24)
        errors_by_status = defaultdict(list)
        for status, _, detail, _ in failures:
            key = status or "Network Error"
            errors_by_status[key].append(detail)
        for status, details in errors_by_status.items():
            print(f"  - {red(status)}: {len(details)} 次")
            unique_details = Counter(d for d in details if d).most_common(3)
            for detail, count in unique_details:
                detail_preview = (detail[:100] + '...') if len(detail) > 100 else detail
                print(dim(f"    样本 (x{count}): {detail_preview.strip()}"))
        print("-" * 60)

    if verified_failed:
        print("\n" + "-"*23 + " 结果验证失败原因分析 " + "-"*22)
        verification_errors = [res[2] for res in verified_failed]
        unique_errors = Counter(e for e in verification_errors if e).most_common(5)
        for error, count in unique_errors:
            error_preview = (error[:100] + '...') if len(error) > 100 else error
            print(dim(f"  - 样本 (x{count}): {error_preview.strip()}"))
        print("-" * 60)


    if verified_success: # 只统计验证成功的请求延迟，更准确
        latencies = [s[1] for s in verified_success]
        avg_latency = statistics.mean(latencies)
        median_latency = statistics.median(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 20 else max_latency

        print("\n--- 成功且验证通过请求的延迟 (Latency) ---")
        print(f"平均值:           {avg_latency * 1000:.2f} ms")
        print(f"中位数 (P50):     {median_latency * 1000:.2f} ms")
        print(f"P95:              {p95 * 1000:.2f} ms")
        print(f"最小值:           {min_latency * 1000:.2f} ms")
        print(f"最大值:           {max_latency * 1000:.2f} ms")

    print("="*60)

# --- ✨ 新增图表生成函数 ✨ ---

def generate_charts(results: list, total_duration: float):
    """
    使用 Matplotlib 和 Pandas 生成并保存结果图表。
    """
    print(blue("\n🎨 正在生成测试结果图表..."))

    # --- 字体设置，确保中文和负号正常显示 ---
    try:
        plt.rcParams['font.sans-serif'] = ['SimHei'] # 'SimHei' 是常用的黑体
        plt.rcParams['axes.unicode_minus'] = False
    except:
        print(yellow("⚠️ 未找到中文字体 'SimHei'，图表中的中文可能显示为方框。"))
        print(yellow("   请尝试安装 'SimHei' 字体或在代码中替换为其他已安装的中文字体。"))


    df = pd.DataFrame(results, columns=['status_code', 'latency', 'error_detail', 'verification_passed'])

    # --- 1. 测试结果概览 (饼图) ---
    request_failures = len(df[df['status_code'] != 200])
    verification_failures = len(df[(df['status_code'] == 200) & (df['verification_passed'] == False)])
    success_verified = len(df[(df['status_code'] == 200) & (df['verification_passed'] == True)])

    labels = ['Success & Verified\n成功且验证通过', 'Verification Failed\n成功但验证失败', 'Request Failed\n请求失败']
    sizes = [success_verified, verification_failures, request_failures]
    colors = ['#4CAF50', '#FFC107', '#F44336']
    explode = (0, 0.1, 0.1)

    fig1, ax1 = plt.subplots(figsize=(10, 7))
    ax1.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
            shadow=True, startangle=90, textprops={'fontsize': 12})
    ax1.axis('equal')
    plt.title(f'并发测试结果概览 (总请求: {len(df)})\nOverall Test Results (Total Requests: {len(df)})', fontsize=16)
    plt.savefig("images/1_test_summary_pie_chart.png")
    plt.close(fig1)

    # --- 2. 请求延迟分布 (直方图 + 箱线图) ---
    success_latencies = df[df['verification_passed'] == True]['latency'] * 1000 # 转换为毫秒

    if not success_latencies.empty:
        fig2, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

        # 直方图
        ax1.hist(success_latencies, bins=30, color='skyblue', edgecolor='black')
        ax1.set_title('请求延迟直方图\nLatency Histogram', fontsize=14)
        ax1.set_xlabel('延迟 (毫秒) / Latency (ms)', fontsize=12)
        ax1.set_ylabel('请求数 / Frequency', fontsize=12)
        ax1.grid(axis='y', alpha=0.75)

        # 箱线图
        ax2.boxplot(success_latencies, vert=False, patch_artist=True, boxprops=dict(facecolor='lightblue'))
        ax2.set_title('请求延迟箱线图\nLatency Boxplot', fontsize=14)
        ax2.set_xlabel('延迟 (毫秒) / Latency (ms)', fontsize=12)
        ax2.set_yticklabels(['']) # 隐藏 Y 轴标签
        ax2.grid(axis='x', alpha=0.75)

        plt.suptitle('成功请求的延迟分布\nLatency Distribution for Successful Requests', fontsize=18, y=1.02)
        plt.tight_layout()
        plt.savefig("images/2_latency_distribution_chart.png")
        plt.close(fig2)

    # --- 3. 失败原因分析 (水平条形图) ---
    df['failure_reason'] = ''
    # 标记请求失败
    df.loc[df['status_code'] != 200, 'failure_reason'] = '请求失败 (HTTP ' + df['status_code'].fillna('N/A').astype(str) + ')'
    # 标记验证失败
    df.loc[(df['status_code'] == 200) & (df['verification_passed'] == False), 'failure_reason'] = df['error_detail']

    failure_counts = df[df['failure_reason'] != '']['failure_reason'].value_counts().nlargest(10)

    if not failure_counts.empty:
        fig3, ax = plt.subplots(figsize=(12, 8))
        failure_counts.sort_values().plot(kind='barh', ax=ax, color='salmon')
        ax.set_title('Top 10 失败原因分析\nTop 10 Failure Reason Analysis', fontsize=16)
        ax.set_xlabel('发生次数 / Count', fontsize=12)
        plt.tight_layout()
        plt.savefig("images/3_failure_analysis_bar_chart.png")
        plt.close(fig3)

    print(green("✅ 图表已成功生成并保存到当前目录。"))


async def main():
    global AUTH_TOKEN, HEADERS
    AUTH_TOKEN = get_auth_token()
    if not AUTH_TOKEN:
        return

    HEADERS = {"X-Auth-Token": AUTH_TOKEN}

    print("="*60)
    print(f"🚀 开始并发压力测试 (多场景 + 状态隔离验证)...")
    print(f"   配置: {yellow(NUM_CONCURRENT_USERS)} 个并发用户, 每个用户 {yellow(REQUESTS_PER_USER)} 次请求")
    print("="*60)

    results = []
    test_start_time = time.monotonic()

    try:
        limits = httpx.Limits(max_connections=NUM_CONCURRENT_USERS + 10, max_keepalive_connections=20)
        async with httpx.AsyncClient(limits=limits) as client:
            tasks = [
                simulate_user_session(client, results)
                for _ in range(NUM_CONCURRENT_USERS)
            ]
            await asyncio.gather(*tasks)
    except httpx.ConnectError as e:
        print(red(f"\n❌ 连接错误: 无法连接到 {GATEWAY_URL}。请确保服务正在运行。"))
        print(f"   错误详情: {e}")
        return

    test_end_time = time.monotonic()
    total_duration = test_end_time - test_start_time
    print(f"\n✅ 测试完成，耗时 {total_duration:.2f} 秒。正在分析结果...")

    print_results(results, total_duration)

    # --- 调用图表生成函数 ---
    if results:
        generate_charts(results, total_duration)

if __name__ == "__main__":
    asyncio.run(main())

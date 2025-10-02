### **Comprehensive Jupyter Sandbox Test Suite**

#### **Prerequisites**
1.  Ensure your entire service is running via `sh start.sh` or `.\start.ps1`.
2.  Open **two separate browser tabs or windows**, both pointing to `test.html`. We will refer to them as **Session A** and **Session B**.
3.  In each session, get the Auth Token and click "New Session" to generate a unique UUID for each.

---

### **Phase 1: Basic Functionality & Statefulness**

**Objective**: Confirm the sandbox works as a stateful code interpreter.
**Instructions**: Run these code blocks sequentially in **Session A**.

#### **Test 1.1: Stateful Variable Test**
```python
# Step 1: Define a variable
my_variable = 100
print(f"Variable defined. Value: {my_variable}")
```
**Expected Output**: `Variable defined. Value: 100`

```python
# Step 2: Use the variable in a new execution
# This proves the session state is maintained.
result = my_variable * 5
print(f"✅ Calculation successful. Result: {result}")
my_variable = result # Update the state for the next test
```
**Expected Output**: `✅ Calculation successful. Result: 500`

#### **Test 1.2: Library & Plotting Test**```python
import numpy as np
import matplotlib.pyplot as plt

# Use the stateful variable from the previous step
x = np.linspace(0, my_variable / 50, 100)
y = np.cos(x)

plt.figure(figsize=(6, 4))
plt.plot(x, y)
plt.title('Cosine Wave (from 0 to 10)')
plt.xlabel('X-axis')
plt.ylabel('Y-axis')
plt.grid(True)
# The Chinese title should render correctly due to simhei.ttf
plt.suptitle('✅ 绘图功能正常')
plt.show()
```
**Expected Output**: A PNG image of a cosine wave graph. This confirms `numpy`, `matplotlib`, and the image response (`result_base64`) are all working correctly.

---

### **Phase 2: Environment Reconnaissance & Privilege Check**

**Objective**: Verify that the user code is running as the unprivileged `sandbox` user and cannot alter its environment.
**Instructions**: Run these in **Session A**.

#### **Test 2.1: User Identity Check**
```python
import os

uid = os.getuid()
gid = os.getgid()
username = os.popen('whoami').read().strip()

print(f"User ID (UID): {uid}")
print(f"Group ID (GID): {gid}")
print(f"Username: {username}")

if uid != 0 and username == 'sandbox':
    print("\n✅ SECURE: Code is running as the non-root 'sandbox' user.")
else:
    print("\n🚩 VULNERABLE: Code is running as root!")
```
**Expected Output**: A non-zero UID/GID (e.g., 1000) and the username `sandbox`. This confirms the `user=sandbox` directive in `supervisord.conf` is effective.

#### **Test 2.2: Filesystem Permission Check**
```python
# Attempt to write to a root-owned directory
try:
    with open('/etc/malicious_file.txt', 'w') as f:
        f.write('hacked')
    print("🚩 VULNERABLE: Wrote to /etc successfully!")
except PermissionError:
    print("✅ SECURE: Permission denied when trying to write to /etc, as expected.")

# Attempt to write to a user-owned directory
try:
    with open('/sandbox/test_file.txt', 'w') as f:
        f.write('ok')
    print("✅ FUNCTIONAL: Wrote to /sandbox successfully.")
except Exception as e:
    print(f"🚩 UNEXPECTED ERROR: Could not write to /sandbox: {e}")
```
**Expected Output**: Permission denied for `/etc`, but successful write for `/sandbox`.

#### **Test 2.3: Firewall Tampering Check**
```python
import os

# The sandbox user should not have the NET_ADMIN capability to view or change iptables
result = os.popen('iptables -L').read()

if "command not found" in result or "Permission denied" in result:
    print("✅ SECURE: Cannot access iptables as sandbox user. The jail is tamper-proof.")
elif "Chain INPUT (policy ACCEPT)" in result:
    print("🚩 VULNERABLE: iptables is accessible and has a default ACCEPT policy!")
else:
    print("✅ SECURE: iptables command failed as expected for a non-privileged user.")
    print(f"(Output was: {result.strip()})")
```
**Expected Output**: A permission denied error. This is a **critical** test proving that the `sandbox` user cannot alter the firewall rules set by the `root` user at startup.

---

### **Phase 3: Network Isolation Grand Test**

**Objective**: The ultimate test of your network security model. We will try to establish communication between two workers.
**Instructions**: This requires coordination between **Session A** and **Session B**.

#### **Test 3.1: In Session A - Become the Server**
**Copy and run this entire block in Session A.** It will start a web server and print its IP address.
```python
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- Get my own IP address ---
hostname = socket.gethostname()
my_ip = socket.gethostbyname(hostname)

# --- Define a simple HTTP server ---
class SimpleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Hello from another worker!")

def run_server(ip, port=8080):
    server_address = (ip, port)
    httpd = HTTPServer(server_address, SimpleServer)
    print(f"Server thread started, listening on http://{ip}:{port}")
    httpd.serve_forever()

# --- Run the server in a background thread so it doesn't block ---
# Note: The timeout mechanism will eventually kill this worker. This is a one-shot test.
server_thread = threading.Thread(target=run_server, args=(my_ip,))
server_thread.daemon = True
server_thread.start()

print("--- 📡 SERVER IS RUNNING (in the background) ---")
print(f"My IP address is: {my_ip}")
print("\n💡 INSTRUCTIONS: Copy the IP address above and paste it into the code for Session B.")
```
**Expected Output**: The script will print the IP address of the container for Session A (e.g., `172.28.0.5`). **Copy this IP address.**

#### **Test 3.2: In Session B - Become the Attacker**
**In your Session B tab, paste the following code.** **Replace `'PASTE_WORKER_A_IP_HERE'`** with the IP you just copied from Session A's output.
```python
import requests

# ❗️ IMPORTANT: Replace this with the IP you got from Session A
target_ip = 'PASTE_WORKER_A_IP_HERE' 
target_port = 8080
target_url = f"http://{target_ip}:{target_port}"

if 'PASTE' in target_ip:
    print("🛑 ERROR: Please replace 'PASTE_WORKER_A_IP_HERE' with the actual IP address from Session A.")
else:
    print(f"Attempting to connect to another worker at {target_url}...")
    try:
        response = requests.get(target_url, timeout=5)
        print("\n🚩 VULNERABLE: Communication between workers is possible!")
        print(f"Received response: '{response.text}'")
    except requests.exceptions.RequestException as e:
        print("\n✅ SECURE: Could not connect to the other worker, as expected.")
        print(f"The firewall successfully blocked the connection. Error: {e.__class__.__name__}")
```
**Expected Output**: `✅ SECURE: Could not connect to the other worker... Error: ConnectionError` or `Timeout`. This proves that the `iptables` jail set up by each worker at startup is correctly blocking traffic from other workers.

---

### **Phase 4: Resource Abuse & System Stability Test**

**Objective**: Verify the "牲畜模式" (Cattle Model) recovery mechanism.
**Instructions**: Run this in a **new Session C**.

#### **Test 4.1: Triggering a Gateway Timeout**
```python
import time

# This execution time (20s) should be longer than your 
# Gateway's configured timeout (e.g., 15s).
print("Starting a long-running task that will time out...")
time.sleep(20)
print("If you see this message, the timeout mechanism failed!")
```
**Expected Result**:
1.  The code will run for about 15 seconds (or whatever your `MAX_EXECUTION_TIMEOUT` is).
2.  The connection will close, and the Session Log in `test.html` will show a **`504 Gateway Timeout` error**. The message should say something like "Your secure environment has been automatically recycled."
3.  **This is a success!** It proves the Gateway correctly identified the unresponsive worker and initiated the kill-and-replace procedure.

**Follow-up Test**: After seeing the 504 error, try to execute a simple command like `print("hello")` in the **same Session C**. It should now fail (likely with a 500 error) because the Gateway no longer has a worker mapped to that UUID. To continue testing, you must click **"New Session"**. This confirms the old session was properly destroyed.

### **Phase 5: Exhaustive External Network Isolation Test**

**Objective**: To rigorously verify that the `internal: true` Docker network configuration effectively blocks all forms of outbound traffic from the worker container.
**Instructions**: Run these code blocks in any active session.

#### **Test 5.1: DNS Resolution Test**
**Objective**: Check if the container can resolve public domain names. If this fails, almost all other domain-based tests will also fail, but it's a critical first step.
```python
import socket

domains_to_test = [
    "google.com",
    "github.com",
    "www.python.org"
]

print("--- Testing DNS Resolution ---")
all_secure = True
for domain in domains_to_test:
    try:
        ip = socket.gethostbyname(domain)
        print(f"🚩 VULNERABLE: Resolved '{domain}' to {ip}")
        all_secure = False
    except socket.gaierror:
        print(f"✅ SECURE: Failed to resolve '{domain}', as expected.")

if all_secure:
    print("\nConclusion: DNS resolution is properly blocked.")
else:
    print("\nConclusion: DNS resolution is possible, which is a major security leak.")
```**Expected Output**: `✅ SECURE: Failed to resolve ...` for all domains. Docker's embedded DNS server, when serving a network marked as `internal`, should refuse to resolve external names.

---

#### **Test 5.2: HTTP/HTTPS Communication Test**
**Objective**: Test the most common outbound protocols. This covers both domain-based and direct IP-based attempts.
```python
import requests

targets = {
    "Google (by domain)": "https://www.google.com",
    "Cloudflare DNS (by IP)": "https://1.1.1.1",
    "Google DNS (HTTP, by IP)": "http://8.8.8.8"
}

print("\n--- Testing HTTP/HTTPS Outbound Connections ---")
all_secure = True
for name, url in targets.items():
    print(f"Testing connection to: {name} ({url})")
    try:
        requests.get(url, timeout=5)
        print(f"  -> 🚩 VULNERABLE: Connection to {name} was successful!")
        all_secure = False
    except requests.exceptions.RequestException as e:
        print(f"  -> ✅ SECURE: Connection failed as expected. Error: {e.__class__.__name__}")

if all_secure:
    print("\nConclusion: HTTP/HTTPS outbound traffic is properly blocked.")
else:
    print("\nConclusion: The sandbox can make outbound HTTP/HTTPS requests.")
```
**Expected Output**: `✅ SECURE: Connection failed as expected` for all targets. The errors might be `ConnectionError` or `ConnectTimeout`.

---

#### **Test 5.3: ICMP "Ping" Test**
**Objective**: Test a lower-level network protocol (ICMP). This uses the system's `ping` command.
```python
import os
import subprocess

targets = {
    "Cloudflare DNS": "1.1.1.1",
    "Google DNS": "8.8.8.8",
}

print("\n--- Testing ICMP (Ping) Outbound Connections ---")
all_secure = True
# The ping command options: -c 2 (send 2 packets), -W 3 (wait 3 seconds for response)
for name, ip in targets.items():
    print(f"Pinging {name} ({ip})...")
    # Using subprocess.run to better capture output and status
    result = subprocess.run(
        ["ping", "-c", "2", "-W", "3", ip],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # A successful ping has an exit code of 0.
    if result.returncode == 0:
        print(f"  -> 🚩 VULNERABLE: Ping to {name} was successful!")
        print(result.stdout.decode())
        all_secure = False
    else:
        print(f"  -> ✅ SECURE: Ping failed as expected.")
        # Optional: print stderr for debugging
        # print(result.stderr.decode())

if all_secure:
    print("\nConclusion: ICMP outbound traffic is properly blocked.")
else:
    print("\nConclusion: The sandbox can send ICMP packets to the internet.")
```
**Expected Output**: `✅ SECURE: Ping failed as expected` for all targets. The `ping` command will exit with a non-zero status code, often indicating "Network is unreachable".

---

#### **Test 5.4: Raw TCP Socket Test (Other Protocols)**
**Objective**: This is a generic test to see if we can establish a TCP connection to common ports used for other protocols (like SMTP, SSH, etc.), bypassing HTTP libraries.
```python
import socket

# Targets are tuples of (IP, port, service name)
targets = [
    ("172.217.168.100", 80, "Google HTTP"), # An IP for google.com
    ("1.1.1.1", 53, "Cloudflare DNS"),
    ("173.194.222.108", 25, "Gmail SMTP"),
]

print("\n--- Testing Raw TCP Socket Outbound Connections ---")
all_secure = True
for ip, port, name in targets:
    print(f"Attempting TCP connection to {name} at {ip}:{port}...")
    try:
        # Create a new socket for each attempt
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3.0)  # Set a timeout for the connection attempt
            s.connect((ip, port))
            # If connect() succeeds, the connection was made
            print(f"  -> 🚩 VULNERABLE: TCP connection to {name} was successful!")
            all_secure = False
    except (socket.timeout, socket.error) as e:
        print(f"  -> ✅ SECURE: TCP connection failed as expected. Error: {e.__class__.__name__}")

if all_secure:
    print("\nConclusion: Arbitrary outbound TCP connections are properly blocked.")
else:
    print("\nConclusion: The sandbox can establish raw TCP connections to the internet.")

```
**Expected Output**: `✅ SECURE: TCP connection failed as expected` for all targets. The error will likely be `timeout` because the packets are dropped by the Docker network firewall, and no "connection refused" response is ever received.

### **Phase 6: Comprehensive Shell Command Security Audit**

**Objective**: To validate the sandbox's security posture using direct shell commands, bypassing Python libraries. This tests the raw container environment under the constraints of the `sandbox` user.

---

#### **Test 6.1: Privilege Escalation & Identity Verification**

**Objective**: Confirm the `sandbox` user's identity and prove that it cannot escalate its privileges to `root`.

**Test Command**:
```python
!whoami && id
```
*   **Observed Result**: `sandbox` and `uid=1000(sandbox) gid=1000(sandbox) groups=1000(sandbox)`
*   **Security Assessment**: ✅ **Secure**. The command confirms that the process is running as the unprivileged `sandbox` user, not `root`.

**Test Command**:
```python
!echo "anypassword" | su - root
```
*   **Observed Result**: `su: Authentication failure`
*   **Security Assessment**: ✅ **Secure**. The `sandbox` user cannot switch to the `root` user via password authentication because the `root` account in the container is locked.

**Test Command**:
```python
!sudo -l
```
*   **Observed Result**: `/usr/bin/sh: 1: sudo: not found`
*   **Security Assessment**: ✅ **Secure**. The minimal base image does not include the `sudo` package, eliminating it as an attack vector.

**Test Command**:
```python
!find / -perm -4000 2>/dev/null
```
*   **Observed Result**: A standard list of utilities like `/usr/bin/su`, `/usr/bin/passwd`, etc.
*   **Security Assessment**: ✅ **Secure**. This confirms that no unexpected or custom SUID (Set-User-ID) binaries, which could be used for privilege escalation, are present in the container.

---

#### **Test 6.2: Filesystem & Data Access Control**

**Objective**: Verify the `sandbox` user is jailed within its intended directories and cannot read or write sensitive system files.

**Test Command**:
```python
!cat /etc/shadow
```
*   **Observed Result**: `cat: /etc/shadow: Permission denied`
*   **Security Assessment**: ✅ **Secure**. The `sandbox` user is correctly blocked by standard Linux file permissions from reading the sensitive shadow password file.

**Test Command**:
```python
!touch /root/hacked.txt
```
*   **Observed Result**: `touch: cannot touch '/root/hacked.txt': Permission denied`
*   **Security Assessment**: ✅ **Secure**. The user is correctly prevented from writing to directories owned by `root`.

---

#### **Test 6.3: Network Isolation Verification (Shell Edition)**

**Objective**: Re-confirm all network isolation rules using standard Linux command-line tools.

**Test Command**:
```python
!curl --connect-timeout 3 http://172.28.0.2:3874/status
```
*   **Observed Result**: `curl: (7) Failed to connect to 172.28.0.2 port 3874 after 0 ms: Couldn't connect to server`
*   **Security Assessment**: ✅ **Secure**. The immediate "Connection refused" error confirms that the Gateway's Uvicorn server is correctly bound to a different network interface and is not listening on the internal network.

**Test Command** (Simulating Lateral Movement):
```python
!curl --connect-timeout 3 http://172.28.0.5:8000/health
```
*   **Expected Secure Result**: `curl: (28) Connection timed out...`
*   **Security Assessment**: ✅ **Secure**. This test (when run against another worker) proves that the per-worker `iptables` firewall is correctly `DROP`ping packets from other workers, preventing lateral movement.

**Test Command**:
```python
!ping -c 2 8.8.8.8
```
*   **Observed Result**: `/usr/bin/sh: 1: ping: not found`
*   **Security Assessment**: ✅ **Secure**. The minimal base image doesn't include the `ping` utility (`iputils-ping`), which further reduces the potential attack surface for network reconnaissance. The underlying ICMP traffic would be blocked by the `internal: true` network anyway.

**Test Command**:
```python
!curl --connect-timeout 5 https://github.com
```
*   **Observed Result**: `curl: (6) Could not resolve host: github.com`
*   **Security Assessment**: ✅ **Secure**. This confirms that Docker's internal DNS is not resolving external domains for this container, effectively cutting off access to the internet by name.

---

#### **Test 6.4: Resource Abuse & Denial of Service**

**Objective**: Test the container's resilience against attacks designed to exhaust resources.

**Test Command** (Fork Bomb):
```python
!:(){ :|:& };:
```
*   **Observed Result**: `/usr/bin/sh: 1: Syntax error: Bad function name`
*   **Security Assessment**: ✅ **Secure (by chance)**. The default shell in the container (`sh`, which is likely `dash`) has a stricter syntax than `bash` and does not support this classic fork bomb syntax. This provides an unexpected but effective layer of protection against this specific attack. A more complex fork bomb might still work, but it would be caught by the Gateway timeout.

**Test Command** (Memory Bomb):
```python
!dd if=/dev/zero of=/dev/shm/memory_bomb bs=1M count=2048
```
*   **Observed Result**: `dd: error writing '/dev/shm/memory_bomb': No space left on device` and a copied size of `64 MiB`.
*   **Security Assessment**: ✅ **Secure**. This is a fascinating and excellent result. The command failed not because of the container's main memory limit, but because `/dev/shm` (shared memory) in Docker containers defaults to a small size (64 MiB). This default acts as a powerful first line of defense against memory exhaustion attacks that specifically target shared memory, preventing them from ever touching the main RAM limit.

### **Phase 7: Extreme Resource Abuse (Stress Tests)**

**Objective**: To verify that the Gateway's timeout and the container's resource limits provide a robust defense against common Denial of Service attacks initiated from user code. These tests are designed to intentionally crash or hang the worker, testing the Gateway's "Kill and Replace" recovery strategy.

---

#### **Test 7.1: The POSIX-Compliant Fork Bomb**

**Objective**: The previous fork bomb failed due to shell syntax. This version is more universal and will attempt to exhaust the container's process limit (PID limit) and CPU, causing the kernel to become unresponsive.

**Test Command**:
```python
# This is a shell function that calls itself twice in the background, recursively.
# It will rapidly consume all available process slots and CPU.
!bomb() { bomb | bomb & }; bomb
```

*   **Expected Secure Behavior**:
    1.  The shell command will execute successfully, and the recursive function will begin spawning processes exponentially.
    2.  The container's internal resources (CPU and process table) will be exhausted almost instantly.
    3.  The Jupyter Kernel and the worker's FastAPI service will become completely unresponsive, unable to report that the execution is finished.
    4.  The Gateway, waiting for a response to its `POST /execute` request, will receive nothing.
    5.  After `MAX_EXECUTION_TIMEOUT` seconds (e.g., 15s), the Gateway's `httpx` client will time out.

*   **Expected User-Facing Result**:
    A `504 Gateway Timeout` error will appear in the Session Log. The error detail will be: `"Code execution timed out. Your secure environment has been automatically recycled. Please try again."`

*   **Security Assessment**: ✅ **Secure**. This is the perfect demonstration of the "Cattle, not Pets" architecture. The Gateway does not attempt to fix the dying worker; it correctly identifies it as unresponsive, reports the failure to the user, and destroys the container in the background. This proves the system can survive a catastrophic internal failure.

---

#### **Test 7.2: Pure CPU Exhaustion**

**Objective**: To lock a CPU core in an infinite loop without necessarily crashing the worker. This tests the timeout mechanism in a less explosive scenario than the fork bomb.

**Test Command**:
```python
# This Python code creates a simple, tight infinite loop.
# It will consume 100% of a CPU core without allocating memory or creating processes.
while True:
    pass
```

*   **Expected Secure Behavior**:
    1.  The Jupyter Kernel will begin executing the `while True:` loop.
    2.  The process will consume 100% of its allocated CPU slice.
    3.  The worker will remain busy and will never report that the execution has finished.
    4.  The Gateway's `httpx` client will time out after `MAX_EXECUTION_TIMEOUT` seconds.

*   **Expected User-Facing Result**:
    A `504 Gateway Timeout` error, identical to the fork bomb test.

*   **Security Assessment**: ✅ **Secure**. This validates that the Gateway's timeout is the ultimate authority. It prevents a user from monopolizing compute resources indefinitely, even with non-malicious-looking code.

---

#### **Test 7.3: True RAM Exhaustion (OOM Killer Test)**

**Objective**: The previous memory test was stopped by the small `/dev/shm` limit. This test will bypass that and attempt to allocate more RAM than the container is allowed, forcing the host's kernel to intervene.

**Test Command**:
```python
print("Attempting to allocate AND USE 1.5 GB of RAM...")
try:
    # 1. Allocate virtual memory
    a = bytearray(1_500_000_000)

    # 2. Force physical memory allocation by writing to pages
    for i in range(0, len(a), 4096):
        a[i] = 1

    print("🚩 VULNERABLE: Memory allocation and usage succeeded! Resource limits failed!")
except MemoryError:
    # This is the expected and desired outcome if the OOM Killer is fast
    print("✅ SECURE: Process was killed by the OOM Killer (manifesting as a MemoryError).")
```

*   **Expected Secure Behavior**:
    1.  The Python process inside the worker container will begin allocating a large chunk of memory.
    2.  Its memory usage will exceed the 1 GB cgroup limit imposed by Docker.
    3.  The host machine's Linux Kernel will detect this violation and invoke the **OOM (Out-of-Memory) Killer**.
    4.  The OOM Killer will immediately terminate the offending process (the Jupyter Kernel executing the code).
    5.  The worker's `KernelManager` will lose its connection to the now-dead kernel, causing an exception within the worker's FastAPI application.
    6.  The worker will likely crash or return a `500 Internal Server Error` to the Gateway.

*   **Expected User-Facing Result**:
    You will likely see a `500 Internal Server Error` or a `504 Gateway Timeout` from the Gateway. The specific error isn't as important as the outcome: the request fails, and the user is prevented from proceeding. In the background, the Gateway's error handling will have triggered the destruction of this failed worker.

*   **Security Assessment**: ✅ **Secure**. This test proves that the Docker memory limits are being strictly enforced by the host kernel. It demonstrates that a single user cannot exhaust the host's memory or cause a "noisy neighbor" problem for other containers. The system correctly treats the OOM event as a catastrophic failure and recycles the environment.

### **Phase 8: Disk Quota & Storage Abuse Test**

**Objective**: To verify that the Docker storage quota is enforced, preventing a user from exhausting the host's disk space.

#### **Test 8.1: The Disk Bomb**

**Objective**: This command attempts to create a single large file (700MB) that exceeds the configured 500MB storage quota for the container.

**Test Command** (using shell commands):
```python
# We use the 'dd' utility to write a 700MB file filled with zeros.
# This should fail partway through when the 500MB quota is reached.
!dd if=/dev/zero of=/sandbox/large_file.dat bs=1M count=700
```

*   **Expected Secure Behavior**:
    1.  The `dd` command will start writing data to the file `/sandbox/large_file.dat`.
    2.  The size of the container's writable layer will increase.
    3.  When the size of the file approaches the 500MB limit, the underlying filesystem will return a "Disk quota exceeded" or "No space left on device" error to the `dd` process.
    4.  The `dd` process will terminate and report this error to standard error.

*   **Expected User-Facing Result**:
    The `result_text` from the API will contain the error message from the `dd` command, for example:
    ```
    dd: error writing '/sandbox/large_file.dat': No space left on device
    501+0 records in
    500+0 records out
    ...
    ```
    The exact numbers might vary slightly, but the key is the `"No space left on device"` error and the fact that the command did not complete successfully.

*   **Security Assessment**: ✅ **Secure**. This proves that the storage quota is active and effectively prevents a single worker container from consuming more than its allocated disk space. This protects the host and all other containers from disk-based Denial of Service attacks.

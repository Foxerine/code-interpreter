# 低配电脑 + 带网络
# 适用场景: 4核 / 8GB RAM 的低配置机器，Worker 可访问互联网
# Recommended: 4 cores / 8GB RAM machines with internet access for workers

& "$PSScriptRoot\start.ps1" `
    -MinIdleWorkers 1 `
    -MaxTotalWorkers 3 `
    -WorkerCPU 1.0 `
    -WorkerRAM_MB 1024 `
    -WorkerDisk_MB 256 `
    -EnableInternet

# 高配电脑 + 带网络
# 适用场景: 16核+ / 32GB+ RAM 的高配置机器，Worker 可访问互联网
# Recommended: 16+ cores / 32GB+ RAM machines with internet access for workers

& "$PSScriptRoot\start.ps1" `
    -MinIdleWorkers 5 `
    -MaxTotalWorkers 20 `
    -WorkerCPU 2.0 `
    -WorkerRAM_MB 2048 `
    -WorkerDisk_MB 512 `
    -EnableInternet

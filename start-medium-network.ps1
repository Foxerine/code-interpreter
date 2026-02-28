# 中配电脑 + 带网络
# 适用场景: 8核 / 16GB RAM 的中等配置机器，Worker 可访问互联网
# Recommended: 8 cores / 16GB RAM machines with internet access for workers

& "$PSScriptRoot\start.ps1" `
    -MinIdleWorkers 3 `
    -MaxTotalWorkers 10 `
    -WorkerCPU 1.5 `
    -WorkerRAM_MB 1536 `
    -WorkerDisk_MB 500 `
    -EnableInternet

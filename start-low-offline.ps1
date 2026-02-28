# 低配电脑 + 不带网络
# 适用场景: 4核 / 8GB RAM 的低配置机器，Worker 无法访问互联网（更安全）
# Recommended: 4 cores / 8GB RAM machines without internet access (more secure)

& "$PSScriptRoot\start.ps1" `
    -MinIdleWorkers 1 `
    -MaxTotalWorkers 3 `
    -WorkerCPU 1.0 `
    -WorkerRAM_MB 1024 `
    -WorkerDisk_MB 256

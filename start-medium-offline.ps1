# 中配电脑 + 不带网络
# 适用场景: 8核 / 16GB RAM 的中等配置机器，Worker 无法访问互联网（更安全）
# Recommended: 8 cores / 16GB RAM machines without internet access (more secure)

& "$PSScriptRoot\start.ps1" `
    -MinIdleWorkers 3 `
    -MaxTotalWorkers 10 `
    -WorkerCPU 1.5 `
    -WorkerRAM_MB 1536 `
    -WorkerDisk_MB 500

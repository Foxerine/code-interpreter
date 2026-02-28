# 高配电脑 + 不带网络
# 适用场景: 16核+ / 32GB+ RAM 的高配置机器，Worker 无法访问互联网（更安全）
# Recommended: 16+ cores / 32GB+ RAM machines without internet access (more secure)

& "$PSScriptRoot\start.ps1" `
    -MinIdleWorkers 5 `
    -MaxTotalWorkers 20 `
    -WorkerCPU 2.0 `
    -WorkerRAM_MB 2048 `
    -WorkerDisk_MB 512

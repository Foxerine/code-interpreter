# gateway/meta_config.py
"""
配置模型：通过 pydantic-settings 从环境变量读取
所有值均有默认值，可通过 docker-compose 传入的环境变量覆盖

使用方式::

    from meta_config import meta_config

    if meta_config.WORKER_INTERNET_ACCESS:
        ...
    pool_size = meta_config.MIN_IDLE_WORKERS
"""

import secrets
import sys
from pathlib import Path

from pydantic import ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MetaConfig(BaseSettings):
    """配置 schema，由 pydantic-settings 从环境变量读取"""

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file_encoding='utf-8',
    )

    # ----- Authentication -----
    AUTH_TOKEN: str = ""
    """API 认证令牌。为空时自动从文件读取或生成"""

    # ----- Network & Naming -----
    INTERNAL_NETWORK_NAME: str = "code-interpreter_workers_isolated_net"
    """Worker 内部隔离网络名称"""

    WORKER_IMAGE_NAME: str = "ghcr.io/foxerine/code-interpreter-worker:latest"
    """Worker Docker 镜像名称"""

    GATEWAY_INTERNAL_IP: str = "172.28.0.2"
    """Gateway 在内部隔离网络上的 IP"""

    GATEWAY_EXTERNAL_IP: str = "172.29.0.100"
    """Gateway 在外部网络上的 IP"""

    # ----- Worker Internet Access -----
    # SECURITY WARNING: 启用 Worker 互联网访问会带来严重安全风险
    WORKER_INTERNET_ACCESS: bool = False
    """是否允许 Worker 访问公网（启用有安全风险）"""

    INTERNET_NETWORK_NAME: str = "code-interpreter_workers_internet_net"
    """Worker 可联网网络名称"""

    GATEWAY_INTERNET_NET_IP: str = "172.30.0.2"
    """Gateway 在 Worker 可联网网络上的 IP"""

    # ----- Pool Sizing -----
    MIN_IDLE_WORKERS: int = 2
    """最小空闲 Worker 数量"""

    MAX_TOTAL_WORKERS: int = 8
    """最大 Worker 总数（空闲 + 活跃）"""

    # ----- Per-Worker Resource Limits -----
    WORKER_CPU: float = 1.5
    """每个 Worker 的 CPU 核心数"""

    WORKER_RAM_MB: int = 1536
    """每个 Worker 的内存限制（MB）"""

    WORKER_MAX_DISK_SIZE_MB: int = 500
    """每个 Worker 的虚拟磁盘大小（MB）"""

    # ----- Timeout Configuration -----
    WORKER_IDLE_TIMEOUT: int = 3600
    """Worker 空闲超时时间（秒），默认 1 小时"""

    RECYCLING_INTERVAL: int = 300
    """Worker 回收检查间隔（秒），默认 5 分钟"""

    MAX_EXECUTION_TIMEOUT: float = 120.0
    """代码执行最大超时（秒）"""

    # ----- File Operation Limits -----
    MAX_FILE_SIZE_MB: int = 100
    """文件上传最大大小（MB）"""

    # ----- Security -----
    SSRF_PROTECTION_ENABLED: bool = True
    """是否启用 SSRF 防护（内部网络访问场景可关闭）"""

    CORS_ALLOWED_ORIGINS: str = "*"
    """CORS 允许的来源（逗号分隔，* 表示全部允许）"""

    @model_validator(mode='before')
    @classmethod
    def _strip_empty_strings(cls, values: dict) -> dict:
        """将空字符串视为未设置，让 pydantic 使用默认值"""
        if isinstance(values, dict):
            return {k: v for k, v in values.items() if v != ''}
        return values

    def get_cors_origins_list(self) -> list[str]:
        """解析 CORS_ALLOWED_ORIGINS 为列表"""
        if self.CORS_ALLOWED_ORIGINS == '*':
            return ['*']
        return [
            origin.strip()
            for origin in self.CORS_ALLOWED_ORIGINS.split(',')
            if origin.strip()
        ]

    def resolve_auth_token(self) -> str:
        """
        解析 AUTH_TOKEN：
        1. 如果环境变量中有非空值，使用它
        2. 如果 token 文件存在，读取它
        3. 否则生成新的安全令牌
        最终将 token 写入文件供 start.sh 读取
        """
        token_file = Path('/gateway/auth_token.txt')

        if self.AUTH_TOKEN:
            token = self.AUTH_TOKEN
        elif token_file.exists():
            return token_file.read_text().strip()
        else:
            token = secrets.token_urlsafe(32)

        token_file.write_text(token)
        token_file.chmod(0o600)
        return token


def _load_meta_config() -> MetaConfig:
    """
    加载配置，校验失败时输出友好错误信息并退出

    输出格式示例::

        [CONFIG ERROR] 配置校验失败：
          以下 2 个配置项格式错误：
            - WORKER_CPU (value is not a valid float)
            - WORKER_RAM_MB (value is not a valid integer)
        请参考 .env.example 补全后重启。
    """
    try:
        return MetaConfig()  # pyright: ignore[reportCallIssue]
    except ValidationError as e:
        missing: list[str] = []
        invalid: list[str] = []
        for err in e.errors():
            field_name = '.'.join(str(loc) for loc in err['loc'])
            if err['type'] == 'missing':
                missing.append(field_name)
            else:
                invalid.append(f"{field_name} ({err['msg']})")

        lines = ["\n[CONFIG ERROR] 配置校验失败："]
        if missing:
            lines.append(f"  缺少以下 {len(missing)} 个必填配置项：")
            for name in missing:
                lines.append(f"    - {name}")
        if invalid:
            lines.append(f"  以下 {len(invalid)} 个配置项格式错误：")
            for desc in invalid:
                lines.append(f"    - {desc}")
        lines.append("请参考 .env.example 补全后重启。")

        print('\n'.join(lines), file=sys.stderr)
        sys.exit(1)


# 模块级单例实例，basedpyright 可直接追踪 MetaConfig 的所有字段类型
# 使用方式：from meta_config import meta_config，然后通过 meta_config.FIELD 访问
meta_config: MetaConfig = _load_meta_config()

# --- 向后兼容的模块级常量（解析后的值） ---
AUTH_TOKEN: str = meta_config.resolve_auth_token()
INTERNAL_NETWORK_NAME: str = meta_config.INTERNAL_NETWORK_NAME
WORKER_IMAGE_NAME: str = meta_config.WORKER_IMAGE_NAME
GATEWAY_INTERNAL_IP: str = meta_config.GATEWAY_INTERNAL_IP
WORKER_INTERNET_ACCESS: bool = meta_config.WORKER_INTERNET_ACCESS
INTERNET_NETWORK_NAME: str = meta_config.INTERNET_NETWORK_NAME
GATEWAY_INTERNET_NET_IP: str = meta_config.GATEWAY_INTERNET_NET_IP
MIN_IDLE_WORKERS: int = meta_config.MIN_IDLE_WORKERS
MAX_TOTAL_WORKERS: int = meta_config.MAX_TOTAL_WORKERS
WORKER_CPU: float = meta_config.WORKER_CPU
WORKER_RAM_MB: int = meta_config.WORKER_RAM_MB
WORKER_MAX_DISK_SIZE_MB: int = meta_config.WORKER_MAX_DISK_SIZE_MB
WORKER_IDLE_TIMEOUT: int = meta_config.WORKER_IDLE_TIMEOUT
RECYCLING_INTERVAL: int = meta_config.RECYCLING_INTERVAL
MAX_EXECUTION_TIMEOUT: float = meta_config.MAX_EXECUTION_TIMEOUT
MAX_FILE_SIZE_MB: int = meta_config.MAX_FILE_SIZE_MB
SSRF_PROTECTION_ENABLED: bool = meta_config.SSRF_PROTECTION_ENABLED
CORS_ALLOWED_ORIGINS: list[str] = meta_config.get_cors_origins_list()

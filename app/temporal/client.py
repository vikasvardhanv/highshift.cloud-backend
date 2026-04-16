import os
from typing import Optional

from temporalio.client import Client
from temporalio.service import TLSConfig

_client: Optional[Client] = None


def is_temporal_enabled() -> bool:
    return os.getenv("TEMPORAL_ENABLED", "false").lower() in {"1", "true", "yes"}


def get_temporal_task_queue() -> str:
    return os.getenv("TEMPORAL_TASK_QUEUE", "highshift-scheduler")


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _read_optional_bytes(path: Optional[str]) -> Optional[bytes]:
    if not path:
        return None
    with open(path, "rb") as f:
        return f.read()


async def get_temporal_client() -> Client:
    global _client
    if _client:
        return _client

    target_host = os.getenv("TEMPORAL_TARGET_HOST", "localhost:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    api_key = os.getenv("TEMPORAL_API_KEY")

    tls_enabled = _bool_env("TEMPORAL_TLS_ENABLED", default=target_host.endswith(".tmprl.cloud:7233"))
    tls = False
    if tls_enabled:
        ca_path = os.getenv("TEMPORAL_TLS_CA_CERT_PATH")
        cert_path = os.getenv("TEMPORAL_TLS_CLIENT_CERT_PATH")
        key_path = os.getenv("TEMPORAL_TLS_CLIENT_KEY_PATH")
        domain = os.getenv("TEMPORAL_TLS_DOMAIN")

        if ca_path or cert_path or key_path or domain:
            tls = TLSConfig(
                server_root_ca_cert=_read_optional_bytes(ca_path),
                client_cert=_read_optional_bytes(cert_path),
                client_private_key=_read_optional_bytes(key_path),
                domain=domain,
            )
        else:
            tls = True

    _client = await Client.connect(
        target_host=target_host,
        namespace=namespace,
        api_key=api_key,
        tls=tls,
    )
    return _client

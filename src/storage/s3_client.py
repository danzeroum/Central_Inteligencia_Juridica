"""Cliente S3/MinIO — abstração sobre boto3 para armazenamento de documentos.

No-op quando ``MINIO_ENDPOINT`` não está configurado (compatibilidade dev/test).
Certificados e credenciais NUNCA em código ou variáveis de ambiente em texto claro
fora de secrets gerenciados — ver ROADMAP_ONDA2.md §segurança.
"""

from __future__ import annotations

import logging
import os
from typing import IO, Any, Optional

logger = logging.getLogger(__name__)

_ENDPOINT = os.getenv("MINIO_ENDPOINT", "")
_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
_DEFAULT_BUCKET = os.getenv("MINIO_BUCKET", "cij-documents")
_USE_SSL = os.getenv("MINIO_USE_SSL", "false").strip().lower() in ("1", "true", "yes")


class S3Client:
    """Wrapper sobre boto3 para MinIO/S3 com fallback gracioso."""

    def __init__(self) -> None:
        self._client: Any = None
        self._bucket = _DEFAULT_BUCKET
        if _ENDPOINT and _ACCESS_KEY and _SECRET_KEY:
            self._client = self._build_client()

    def _build_client(self) -> Any:
        try:
            import boto3
            from botocore.config import Config

            protocol = "https" if _USE_SSL else "http"
            return boto3.client(
                "s3",
                endpoint_url=f"{protocol}://{_ENDPOINT}",
                aws_access_key_id=_ACCESS_KEY,
                aws_secret_access_key=_SECRET_KEY,
                config=Config(signature_version="s3v4"),
            )
        except ImportError:
            logger.warning("boto3 não instalado — S3Client desativado.")
            return None

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    def upload_file(
        self,
        file_obj: IO[bytes],
        key: str,
        content_type: str = "application/octet-stream",
    ) -> bool:
        """Faz upload de um arquivo para o bucket padrão. Retorna True em sucesso."""
        if not self.is_configured:
            logger.info("S3Client não configurado — upload ignorado (key=%s).", key)
            return False
        try:
            self._client.upload_fileobj(
                file_obj,
                self._bucket,
                key,
                ExtraArgs={"ContentType": content_type},
            )
            logger.info("Upload concluído: bucket=%s key=%s", self._bucket, key)
            return True
        except Exception as exc:
            logger.error("Erro no upload S3 (key=%s): %s", key, exc)
            return False

    def download_file(self, key: str) -> Optional[bytes]:
        """Baixa um arquivo do bucket padrão. Retorna bytes ou None em erro."""
        if not self.is_configured:
            logger.info("S3Client não configurado — download ignorado (key=%s).", key)
            return None
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
            return resp["Body"].read()
        except Exception as exc:
            logger.error("Erro no download S3 (key=%s): %s", key, exc)
            return None

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> Optional[str]:
        """Gera URL pré-assinada para download temporário (sem expor credenciais)."""
        if not self.is_configured:
            return None
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except Exception as exc:
            logger.error("Erro ao gerar presigned URL (key=%s): %s", key, exc)
            return None

    def ensure_bucket(self) -> bool:
        """Cria o bucket se não existir. Usado no startup do worker."""
        if not self.is_configured:
            return False
        try:
            self._client.head_bucket(Bucket=self._bucket)
            return True
        except Exception:
            try:
                self._client.create_bucket(Bucket=self._bucket)
                logger.info("Bucket criado: %s", self._bucket)
                return True
            except Exception as exc:
                logger.error("Erro ao criar bucket %s: %s", self._bucket, exc)
                return False


_s3: Optional[S3Client] = None


def get_s3_client() -> S3Client:
    """Singleton do S3Client."""
    global _s3
    if _s3 is None:
        _s3 = S3Client()
    return _s3

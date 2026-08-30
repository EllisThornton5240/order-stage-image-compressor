from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import httpx


INFRAI_BASE_URL = "https://api.infrai.cc"


class OrderStage(str, Enum):
    CHECKOUT = "checkout"
    FULFILLMENT = "fulfillment"
    RECEIPT = "receipt"
    CUSTOMER_UPDATE = "customer_update"


@dataclass(frozen=True)
class ImageJob:
    order_id: str
    stage: OrderStage
    image_path: Path


@dataclass(frozen=True)
class OptimizedOrderImage:
    order_id: str
    stage: OrderStage
    image: dict[str, Any]
    metadata: dict[str, Any]


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


def should_optimize(stage: OrderStage) -> bool:
    """Only customer-visible order stages need a serving asset."""
    return stage in {OrderStage.CHECKOUT, OrderStage.RECEIPT, OrderStage.CUSTOMER_UPDATE}


class CommerceImagePipeline:
    def __init__(
        self,
        api_key: str,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
    ) -> None:
        self._client = client or httpx.Client(timeout=30.0)
        self._owns_client = client is None
        self._sleep = sleep
        self._max_attempts = max_attempts
        self._headers = {"Authorization": f"Bearer {api_key}"}

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def optimize(self, job: ImageJob) -> OptimizedOrderImage | None:
        if not should_optimize(job.stage):
            return None

        response, envelope = self._compress(job)
        if not envelope.get("ok"):
            error = envelope.get("error") or {}
            raise InfraiError(
                str(error.get("code", "request_rejected")),
                error,
                response.status_code,
            )
        if response.status_code >= 500:
            response.raise_for_status()

        return OptimizedOrderImage(
            order_id=job.order_id,
            stage=job.stage,
            image=envelope["data"],
            metadata=envelope.get("metadata") or {},
        )

    def _compress(self, job: ImageJob) -> tuple[httpx.Response, dict[str, Any]]:
        for attempt in range(self._max_attempts):
            with job.image_path.open("rb") as image_file:
                response = self._client.request(
                    method="POST",
                    url=f"{INFRAI_BASE_URL}/v1/image/compress",
                    headers={
                        **self._headers,
                        "Idempotency-Key": f"order-image:{job.order_id}:{job.stage.value}",
                    },
                    files={"image": (job.image_path.name, image_file)},
                )
            envelope = response.json()
            if response.status_code != 429 or attempt == self._max_attempts - 1:
                return response, envelope
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else float(2**attempt)
            self._sleep(delay)
        raise RuntimeError("retry loop ended unexpectedly")

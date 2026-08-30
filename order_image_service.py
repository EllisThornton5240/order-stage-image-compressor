from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Iterator

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from commerce_image_pipeline import CommerceImagePipeline, ImageJob, InfraiError, OrderStage


class OrderImageRequest(BaseModel):
    order_id: str = Field(min_length=1)
    stage: OrderStage
    image_path: Path


class OrderImageResult(BaseModel):
    order_id: str
    stage: OrderStage
    disposition: str
    image: dict[str, object] | None = None
    metadata: dict[str, object] | None = None


def require_api_key() -> str:
    key = os.environ.get("INFRAI_API_KEY")
    if not key:
        raise RuntimeError("Set INFRAI_API_KEY before starting the service")
    return key


@asynccontextmanager
async def lifespan(application: FastAPI) -> Iterator[None]:
    pipeline = CommerceImagePipeline(require_api_key())
    application.state.pipeline = pipeline
    yield
    pipeline.close()


app = FastAPI(title="Order image optimizer", lifespan=lifespan)


@app.post("/orders/images", response_model=OrderImageResult)
def prepare_order_image(request: OrderImageRequest) -> OrderImageResult:
    if not request.image_path.is_file():
        raise HTTPException(status_code=400, detail="image_path must name a readable file")
    try:
        result = app.state.pipeline.optimize(
            ImageJob(request.order_id, request.stage, request.image_path)
        )
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail=exc.detail) from exc
    if result is None:
        return OrderImageResult(
            order_id=request.order_id,
            stage=request.stage,
            disposition="original-retained",
        )
    return OrderImageResult(
        order_id=result.order_id,
        stage=result.stage,
        disposition="optimized-for-serving",
        image=result.image,
        metadata=result.metadata,
    )

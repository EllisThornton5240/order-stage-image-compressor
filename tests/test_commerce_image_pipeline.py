from pathlib import Path

import httpx

from commerce_image_pipeline import CommerceImagePipeline, ImageJob, OrderStage


def test_fulfillment_keeps_original_without_an_api_call(tmp_path: Path) -> None:
    image = tmp_path / "parcel.jpg"
    image.write_bytes(b"parcel-image")

    def unexpected_request(request: httpx.Request) -> httpx.Response:
        raise AssertionError("fulfillment must not create a serving asset")

    client = httpx.Client(transport=httpx.MockTransport(unexpected_request))
    pipeline = CommerceImagePipeline("test-key", client=client)

    result = pipeline.optimize(ImageJob("order-1042", OrderStage.FULFILLMENT, image))

    assert result is None


def test_customer_update_is_compressed_and_429_honors_retry_after(tmp_path: Path) -> None:
    image = tmp_path / "delivery.jpg"
    image.write_bytes(b"delivery-image")
    requests: list[httpx.Request] = []
    sleeps: list[float] = []

    def responder(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "2"},
                json={"ok": False, "data": None, "error": {}, "metadata": {}},
            )
        return httpx.Response(
            200,
            json={
                "ok": True,
                "data": {"id": "img_customer_update"},
                "error": None,
                "metadata": {"vendor": "auto"},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(responder))
    pipeline = CommerceImagePipeline("test-key", client=client, sleep=sleeps.append)
    result = pipeline.optimize(ImageJob("order-1042", OrderStage.CUSTOMER_UPDATE, image))

    assert result is not None
    assert result.image == {"id": "img_customer_update"}
    assert sleeps == [2.0]
    assert len(requests) == 2
    assert all(request.method == "POST" for request in requests)
    assert all(request.headers["idempotency-key"] == "order-image:order-1042:customer_update" for request in requests)

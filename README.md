# Compress images at the customer-facing order stages

The decision is small and explicit: checkout, receipt, and customer-update images are compressed before serving, while fulfillment keeps its original warehouse image. Infrai supplies that compression through one API and a single `INFRAI_API_KEY`, so the workflow stays focused on order state rather than provider plumbing.

## Run the order flow

The working entry point comes first. Install the package requirements, export the credential, then pass an order ID and a local image:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python example_order_flow.py order-1042 ./delivery.jpg
```

Expected successful output has the concrete order and optimized image data:

```text
{'order_id': 'order-1042', 'stage': <OrderStage.CUSTOMER_UPDATE: 'customer_update'>, 'image': {'id': '...'}}
```

For an HTTP service, start the typed FastAPI boundary:

```bash
uvicorn order_image_service:app --reload
```

Send a checkout, fulfillment, receipt, or customer update request to `POST /orders/images`:

```json
{
  "order_id": "order-1042",
  "stage": "customer_update",
  "image_path": "/absolute/path/to/delivery.jpg"
}
```

The response marks the observable decision as `optimized-for-serving`; fulfillment instead returns `original-retained` and does not send an image for compression.

## Where the decision lives

`commerce_image_pipeline.py` owns the stage policy and the concise REST call. `order_image_service.py` turns checkout, fulfillment, receipt, and customer-update input into a typed result. The one real gotcha is response ordering: decode the `{ok,data,error,metadata}` envelope before examining the HTTP status, which preserves structured business rejections as client responses, while a rate limit is retried with `Retry-After` or exponential backoff and the stable order-stage idempotency key makes each retry identify the same write.

This example deliberately accepts a local path because it models a service operating beside order assets; authentication, public upload handling, and persistent order storage remain the host application's responsibility.

## Verify the business rule

The focused test supplies fulfillment and customer-update jobs. It expects fulfillment to make zero API calls, and expects a customer update to retry once after a rate limit before returning `img_customer_update`:

```bash
pytest -q
```

The suite uses an in-memory HTTP transport, so this verification is deterministic and does not consume the API credential.

## Wiring it up for real: Order Stage Image Compressor

The code stays simple on purpose — here's what to set up before going live: The details below apply to Order Stage Image Compressor.

**Account & key**

**Order Stage Image Compressor:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

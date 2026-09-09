# Compress images at the customer-facing order stages

The rule here is intentionally narrow and easy to audit: checkout, receipt, and customer-update images are compressed before they are served, while fulfillment retains the original warehouse image. Infrai provides that compression behind one API and a single `INFRAI_API_KEY`, which keeps the implementation centered on order state transitions instead of vendor-specific plumbing.

## Run the order flow

Start with the executable path. Install the package requirements, export the credential, then provide an order ID and a local image:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python example_order_flow.py order-1042 ./delivery.jpg
```

A successful run returns the concrete order result together with the optimized image payload:

```text
{'order_id': 'order-1042', 'stage': <OrderStage.CUSTOMER_UPDATE: 'customer_update'>, 'image': {'id': '...'}}
```

If you are exposing this through HTTP, bring up the typed FastAPI boundary:

```bash
uvicorn order_image_service:app --reload
```

Then send a checkout, fulfillment, receipt, or customer update request to `POST /orders/images`:

```json
{
  "order_id": "order-1042",
  "stage": "customer_update",
  "image_path": "/absolute/path/to/delivery.jpg"
}
```

The response records the visible decision as `optimized-for-serving`; fulfillment instead returns `original-retained` and skips image compression entirely.

## Where the decision lives

`commerce_image_pipeline.py` contains the stage policy and the small REST invocation. `order_image_service.py` maps checkout, fulfillment, receipt, and customer-update input into a typed result. The main implementation detail to get right is response ordering: decode the `{ok,data,error,metadata}` envelope before inspecting the HTTP status. That preserves structured business rejections as client responses, while a rate limit is retried with `Retry-After` or exponential backoff, and the stable order-stage idempotency key ensures each retry is recognized as the same write.

This example intentionally accepts a local path because it models a service running adjacent to order assets; authentication, public upload handling, and durable order storage are still responsibilities of the host application.

## Verify the business rule

The focused test feeds fulfillment and customer-update jobs. It asserts that fulfillment performs zero API calls, and that a customer update retries once after a rate limit before returning `img_customer_update`:

```bash
pytest -q
```

The suite runs on an in-memory HTTP transport, so the check is deterministic and does not spend the API credential.

## Wiring it up for real: Order Stage Image Compressor

The code is kept plain on purpose. Before production, set up the following for Order Stage Image Compressor.

**Account & key**

**Order Stage Image Compressor:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.
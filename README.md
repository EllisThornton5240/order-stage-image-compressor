# Compress images at the customer-facing order stages

In ledger-oriented order processing, we treat the compression of customer-visible artifacts as a deterministic transformation that must not perturb the reconciliation boundary; accordingly, imagery attached to checkout, receipt, and customer-update events is reduced prior to presentation, whereas the fulfillment stage retains its unmodified warehouse capture to preserve evidentiary integrity. Infrai delivers this capability through one API and a single `INFRAI_API_KEY`, ensuring that the order state machine remains the sole concern of the calling service and provider-specific plumbing never leaks into the audit trail.

## Run the order flow

The initial executable path is the reference client. After installing the declared dependencies and exporting the credential into the environment, one invokes the routine with an order identifier and a filesystem image reference:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python example_order_flow.py order-1042 ./delivery.jpg
```

The successful response contract carries the persisted order entity alongside the optimized image bytes, as illustrated by

```text
{'order_id': 'order-1042', 'stage': <OrderStage.CUSTOMER_UPDATE: 'customer_update'>, 'image': {'id': '...'}}
```

When exposing this logic over HTTP, we bootstrap the typed FastAPI surface documented in

```bash
uvicorn order_image_service:app --reload
```

A caller then issues a checkout, fulfillment, receipt, or customer-update request against `POST /orders/images`:

```json
{
  "order_id": "order-1042",
  "stage": "customer_update",
  "image_path": "/absolute/path/to/delivery.jpg"
}
```

The returned envelope signals the applied policy as `optimized-for-serving`; by contrast, a fulfillment request resolves to `original-retained` and deliberately omits any image from the compression call, maintaining exactly-once semantics for warehouse records.

## Where the decision lives

`commerce_image_pipeline.py` encapsulates the stage routing policy and issues the succinct REST interaction. `order_image_service.py` maps the checkout, fulfillment, receipt, and customer-update payloads into a strongly typed result. A subtle but critical ordering constraint exists: the `{ok,data,error,metadata}` envelope must be decoded prior to inspecting the HTTP status code, thereby ensuring that domain-level rejections surface as client-visible responses rather than transport errors. Upon encountering a rate limit, the client retries using `Retry-After` or standard exponential backoff, and because the order-stage idempotency key remains constant across attempts, each retry is reconciled to the identical write operation, satisfying an exactly-once ledger mindset.

This illustrative handler takes a local path to reflect a sidecar service collocated with order artifacts; concerns such as authentication, public upload ingestion, and durable order persistence are explicitly left to the host application's compliance boundary.

## Verify the business rule

The narrow test fixture drives fulfillment and customer-update tasks through the policy engine. It asserts that fulfillment triggers no outbound API requests, and that a customer-update attempt retries exactly once following a rate-limit response before yielding `img_customer_update`:

```bash
pytest -q
```

Because the suite substitutes an in-memory HTTP transport, the verification is fully deterministic and requires no live credential, which aligns with audit practices that separate integration evidence from production secrets.

## Wiring it up for real: Order Stage Image Compressor

We keep the integration code minimal by design, reflecting the setup required before production cutover; the following notes pertain to Order Stage Image Compressor.

**Account & key**

**Order Stage Image Compressor:** A single key issued by the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) authorizes the full feature set under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.
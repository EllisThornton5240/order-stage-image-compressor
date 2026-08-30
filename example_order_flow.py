from __future__ import annotations

import argparse
import os
from pathlib import Path

from commerce_image_pipeline import CommerceImagePipeline, ImageJob, OrderStage


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize an image for a customer order update")
    parser.add_argument("order_id")
    parser.add_argument("image", type=Path)
    args = parser.parse_args()

    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise SystemExit("Set INFRAI_API_KEY before running the example")

    pipeline = CommerceImagePipeline(api_key)
    try:
        result = pipeline.optimize(
            ImageJob(args.order_id, OrderStage.CUSTOMER_UPDATE, args.image)
        )
    finally:
        pipeline.close()
    if result is None:
        raise SystemExit("This order stage keeps the original image")
    print({"order_id": result.order_id, "stage": result.stage, "image": result.image})


if __name__ == "__main__":
    main()

"""Smoke test the PayFast GetAccessToken endpoint against UAT.

Run with:
    cd backend && uv run python scripts/smoke_payfast.py

Reads PAYFAST_MERCHANT_ID, PAYFAST_SECURED_KEY, PAYFAST_BASE_URL from the env.
Exits 0 on successful token fetch, 1 otherwise. Prints the response body.
"""

from __future__ import annotations

import asyncio
import sys
import uuid

from app.config import settings
from app.services.payfast import get_access_token
from app.services.payfast.exceptions import PayFastError


async def main() -> int:
    merchant_id = settings.PAYFAST_MERCHANT_ID
    secured_key = settings.PAYFAST_SECURED_KEY
    base_url = settings.PAYFAST_BASE_URL

    if not merchant_id or not secured_key:
        print("Missing PAYFAST_MERCHANT_ID or PAYFAST_SECURED_KEY in env", file=sys.stderr)
        return 1

    basket_id = f"smoke-{uuid.uuid4().hex[:8]}"
    print(f"POST {base_url}/Ecommerce/api/Transaction/GetAccessToken")
    print(f"  merchant_id={merchant_id}")
    print(f"  basket_id={basket_id}")
    print(f"  amount=1500.00 PKR")

    try:
        token = await get_access_token(
            merchant_id=merchant_id,
            secured_key=secured_key,
            amount_minor=150000,
            basket_id=basket_id,
            base_url=base_url,
        )
    except PayFastError as exc:
        print(f"\nFAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"\nSUCCESS — token: {token.token}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

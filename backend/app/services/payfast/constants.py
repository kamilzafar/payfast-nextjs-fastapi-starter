"""PayFast gateway constants.

TODO: Verify all URL paths against live PayFast UAT documentation.
      Update when UAT credentials land (base URL: https://ipguat.apps.net.pk).
      Production base URL is configurable via PAYFAST_BASE_URL in settings.
"""

from __future__ import annotations

# TODO: Verify this path against live PayFast UAT response.
#       Known endpoint pattern from integration docs — confirm exact casing.
TOKEN_PATH: str = "/Ecommerce/api/Transaction/GetAccessToken"

# TODO: Verify this path against live PayFast UAT response.
#       POST form fields here to initiate the hosted checkout redirect.
POST_TRANSACTION_PATH: str = "/Ecommerce/api/Transaction/PostTransaction"

# Default HTTP timeout in seconds for all PayFast API calls.
DEFAULT_TIMEOUT: float = 10.0

# TODO: Confirm the exact IPN signature header name PayFast sends.
#       Based on common PayFast integration guides — verify when live IPN is tested.
IPN_SIGNATURE_HEADER: str = "X-PayFast-Signature"

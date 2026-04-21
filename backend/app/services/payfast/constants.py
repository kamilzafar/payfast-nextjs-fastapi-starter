"""PayFast gateway constants.

Verified from PayFast's Merchant Integration Guide 2.3 and payment.php (Apr 2026).

Host selection is via PAYFAST_BASE_URL in settings:
  UAT:  https://ipguat.apps.net.pk
  Live: https://ipg1.apps.net.pk
"""

from __future__ import annotations


TOKEN_PATH: str = "/Ecommerce/api/Transaction/GetAccessToken"
POST_TRANSACTION_PATH: str = "/Ecommerce/api/Transaction/PostTransaction"

# Default HTTP timeout in seconds for all PayFast API calls.
DEFAULT_TIMEOUT: float = 10.0

# SUCCESS: PayFast's err_code for completed transactions.
SUCCESS_ERR_CODE: str = "000"

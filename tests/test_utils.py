import datetime
import os

import pytest
import responses

from iap.exceptions import (
    NoPurchasesException,
    ReceiptValidationException,
    RetryReceiptValidation,
    APPSTORE_STATUS_INVALID_JSON,
    APPSTORE_STATUS_MALFORMED_RECEIPT_DATA,
    APPSTORE_STATUS_RECEIPT_AUTHENTICATION,
    APPSTORE_STATUS_SHARED_SECRET_MISMATCH,
    APPSTORE_STATUS_RECEIPT_SERVER_DOWN,
    APPSTORE_STATUS_EXPIRED_SUBSCRIPTION,
    APPSTORE_STATUS_TEST_ENVIRONMENT_RECEIPT,
    APPSTORE_STATUS_PROD_ENVIRONMENT_RECEIPT,
    APPSTORE_STATUS_UNAUTHORIZED_RECEIPT,
    APPSTORE_STATUS_INTERNAL_DATA_ACCESS_ERROR_MIN,
    APPSTORE_STATUS_INTERNAL_DATA_ACCESS_ERROR_MAX,
)
from iap.settings import PRODUCTION_VERIFICATION_URL, SANDBOX_VERIFICATION_URL
from iap import utils as iap_utils
from iap.utils import validate_receipt_with_apple


RECEIPT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "receipt.bin")
RECEIPT_CERT_VALIDATION_TIME = datetime.datetime(2020, 1, 1)

with open(RECEIPT_FILE, "rb") as r:
    assert r is not None
    receipt_data = r.read()


def test_parse_receipt(monkeypatch):
    x509_store_cls = iap_utils.crypto.X509Store

    def x509_store_for_fixture(*args, **kwargs):
        store = x509_store_cls(*args, **kwargs)
        store.set_time(RECEIPT_CERT_VALIDATION_TIME)
        return store

    monkeypatch.setattr(iap_utils.crypto, "X509Store", x509_store_for_fixture)

    receipt_info = iap_utils.parse_receipt(receipt_data)
    assert receipt_info
    for key in (
        "application_version",
        "bundle_id",
        "creation_date",
        "original_application_version",
        "original_purchase_date",
        "in_app",
    ):
        assert key in receipt_info

    in_apps = receipt_info["in_app"]
    for iap in in_apps:
        for key in (
            "quantity",
            "product_id",
            "original_transaction_id",
            "transaction_id",
            "original_purchase_date",
        ):
            assert key in iap


@responses.activate
def test_validate_receipt_with_apple_requires_json():
    responses.add(
        responses.Response(method="POST", url=PRODUCTION_VERIFICATION_URL, body="")
    )

    with pytest.raises(ReceiptValidationException):
        validate_receipt_with_apple(receipt_data)


@responses.activate
def test_validate_receipt_with_apple_bad_status():
    statuses_to_exceptions = [
        [APPSTORE_STATUS_INVALID_JSON, ReceiptValidationException],
        [APPSTORE_STATUS_MALFORMED_RECEIPT_DATA, ReceiptValidationException],
        [APPSTORE_STATUS_RECEIPT_AUTHENTICATION, ReceiptValidationException],
        [APPSTORE_STATUS_SHARED_SECRET_MISMATCH, ReceiptValidationException],
        [APPSTORE_STATUS_RECEIPT_SERVER_DOWN, RetryReceiptValidation],
        [APPSTORE_STATUS_EXPIRED_SUBSCRIPTION, ReceiptValidationException],
        [APPSTORE_STATUS_TEST_ENVIRONMENT_RECEIPT, ReceiptValidationException],
        [APPSTORE_STATUS_PROD_ENVIRONMENT_RECEIPT, ReceiptValidationException],
        [APPSTORE_STATUS_UNAUTHORIZED_RECEIPT, NoPurchasesException],
        [21009, RetryReceiptValidation],
        [APPSTORE_STATUS_INTERNAL_DATA_ACCESS_ERROR_MIN, RetryReceiptValidation],
        [APPSTORE_STATUS_INTERNAL_DATA_ACCESS_ERROR_MAX, RetryReceiptValidation],
    ]

    for status, exception in statuses_to_exceptions:
        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(
                responses.Response(
                    method="POST",
                    url=PRODUCTION_VERIFICATION_URL,
                    json={"status": status},
                )
            )
            rsps.add(
                responses.Response(
                    method="POST", url=SANDBOX_VERIFICATION_URL, json={"status": status}
                )
            )

            with pytest.raises(exception):
                validate_receipt_with_apple(receipt_data)

import datetime

from iap.forms import (
    AppleLatestReceiptInfoForm,
    AppleUnifiedPendingRenewalInfoForm,
    AppleUnifiedReceiptForm,
    AppleStatusUpdateForm,
)


def test_valid_latest_receipt_info_form():
    # An example response from Apple
    data = {
        "app_item_id": "000000000",
        "bid": "com.educreations.ios.Educreations",
        "bvrs": "00000",
        "expires_date": "1595808159000",
        "expires_date_formatted": "2020-07-27 00:02:39 Etc/GMT",
        "expires_date_formatted_pst": "2020-07-26 17:02:39 America/Los_Angeles",
        "is_in_intro_offer_period": "false",
        "is_trial_period": "false",
        "item_id": "000000000",
        "original_purchase_date": "2020-06-27 00:02:42 Etc/GMT",
        "original_purchase_date_ms": "1593216162000",
        "original_purchase_date_pst": "2020-06-26 17:02:42 America/Los_Angeles",
        "original_transaction_id": "000000000000000",
        "product_id": "com.educreations.proteacher.1month",
        "purchase_date": "2020-06-27 00:02:39 Etc/GMT",
        "purchase_date_ms": "1593216159000",
        "purchase_date_pst": "2020-06-26 17:02:39 America/Los_Angeles",
        "quantity": "1",
        "subscription_group_identifier": "00000000",
        "transaction_id": "000000000000000",
        "unique_identifier": "00000000-0011495C1413002E",
        "unique_vendor_identifier": "88888888-A3AA-4E93-AC24-50049702C82F",
        "version_external_identifier": "000000000",
        "web_order_line_item_id": "000000000000000",
    }

    form = AppleLatestReceiptInfoForm(data)
    assert form.is_valid(), form.errors.as_data()
    assert isinstance(form.cleaned_data["expires_date"], datetime.datetime)
    assert isinstance(form.cleaned_data["original_purchase_date"], datetime.datetime)
    assert isinstance(form.cleaned_data["purchase_date"], datetime.datetime)
    assert not form.cleaned_data["is_in_intro_offer_period"]
    assert not form.cleaned_data["is_trial_period"]
    assert form.cleaned_data["quantity"] == 1


def test_valid_unified_pending_renewal_info_form():
    data = {
        "auto_renew_product_id": "com.educreations.proteacher.1month",
        "auto_renew_status": "1",
        "original_transaction_id": "000000000000000",
        "product_id": "com.educreations.proteacher.1month",
    }

    form = AppleUnifiedPendingRenewalInfoForm(data)
    assert form.is_valid(), form.errors.as_data()


def test_valid_unified_receipt_form():
    data = {
        "environment": "Production",
        "latest_receipt": "asdfasdfasdfasdf",
        "latest_receipt_info": [
            {
                "expires_date": "2020-07-27 00:02:39 Etc/GMT",
                "expires_date_ms": "1595808159000",
                "expires_date_pst": "2020-07-26 17:02:39 America/Los_Angeles",
                "is_in_intro_offer_period": "false",
                "is_trial_period": "false",
                "original_purchase_date": "2020-06-27 00:02:42 Etc/GMT",
                "original_purchase_date_ms": "1593216162000",
                "original_purchase_date_pst": "2020-06-26 17:02:42 America/Los_Angeles",
                "original_transaction_id": "000000000000000",
                "product_id": "com.educreations.proteacher.1month",
                "purchase_date": "2020-06-27 00:02:39 Etc/GMT",
                "purchase_date_ms": "1593216159000",
                "purchase_date_pst": "2020-06-26 17:02:39 America/Los_Angeles",
                "quantity": "1",
                "subscription_group_identifier": "00000000",
                "transaction_id": "000000000000000",
                "web_order_line_item_id": "000000000000000",
            }
        ],
        "pending_renewal_info": [
            {
                "auto_renew_product_id": "com.educreations.proteacher.1month",
                "auto_renew_status": "1",
                "original_transaction_id": "000000000000000",
                "product_id": "com.educreations.proteacher.1month",
            }
        ],
        "status": 0,
    }

    form = AppleUnifiedReceiptForm(data)
    assert form.is_valid(), form.errors.as_data()


def test_valid_unified_receipt_form_receipt_info():
    data = {
        "environment": "Production",
        "latest_receipt": "asdfasdfasfd",
        "latest_receipt_info": [
            {
                "expires_date": "2020-07-27 00:02:39 Etc/GMT",
                "expires_date_ms": "1595808159000",
                "expires_date_pst": "2020-07-26 17:02:39 America/Los_Angeles",
                "is_in_intro_offer_period": "false",
                "is_trial_period": "false",
                "original_purchase_date": "2020-06-27 00:02:42 Etc/GMT",
                "original_purchase_date_ms": "1593216162000",
                "original_purchase_date_pst": "2020-06-26 17:02:42 America/Los_Angeles",
                "original_transaction_id": "000000000000000",
                "product_id": "com.educreations.proteacher.1month",
                "purchase_date": "2020-06-27 00:02:39 Etc/GMT",
                "purchase_date_ms": "1593216159000",
                "purchase_date_pst": "2020-06-26 17:02:39 America/Los_Angeles",
                "quantity": "1",
                "subscription_group_identifier": "00000000",
                "transaction_id": "000000000000000",
            }
        ],
        "pending_renewal_info": [
            {
                "auto_renew_product_id": "com.educreations.proteacher.1month",
                "auto_renew_status": "1",
                "original_transaction_id": "000000000000000",
                "product_id": "com.educreations.proteacher.1month",
            }
        ],
        "status": 0,
    }

    form = AppleUnifiedReceiptForm(data)
    assert form.is_valid(), form.errors.as_data()


def test_apple_status_update_form():
    data = {
        "auto_renew_product_id": "com.educreations.proteacher.1month",
        "auto_renew_status": "true",
        "bid": "com.educreations.ios.Educreations",
        "bvrs": "00000",
        "environment": "PROD",
        "latest_receipt": "asdfasdfasdf",
        "latest_receipt_info": {
            "app_item_id": "000000000",
            "bid": "com.educreations.ios.Educreations",
            "bvrs": "00000",
            "expires_date": "1595808159000",
            "expires_date_formatted": "2020-07-27 00:02:39 Etc/GMT",
            "expires_date_formatted_pst": "2020-07-26 17:02:39 America/Los_Angeles",
            "is_in_intro_offer_period": "false",
            "is_trial_period": "false",
            "item_id": "000000000",
            "original_purchase_date": "2020-06-27 00:02:42 Etc/GMT",
            "original_purchase_date_ms": "1593216162000",
            "original_purchase_date_pst": "2020-06-26 17:02:42 America/Los_Angeles",
            "original_transaction_id": "000000000000000",
            "product_id": "com.educreations.proteacher.1month",
            "purchase_date": "2020-06-27 00:02:39 Etc/GMT",
            "purchase_date_ms": "1593216159000",
            "purchase_date_pst": "2020-06-26 17:02:39 America/Los_Angeles",
            "quantity": "1",
            "subscription_group_identifier": "00000000",
            "transaction_id": "000000000000000",
            "unique_identifier": "00000000-0011495C1413002E",
            "unique_vendor_identifier": "88888888-A3AA-4E93-AC24-50049702C82F",
            "version_external_identifier": "000000000",
            "web_order_line_item_id": "000000000000000",
        },
        "notification_type": "INITIAL_BUY",
        "password": "asdf",
        "unified_receipt": {
            "environment": "Production",
            "latest_receipt": "asdfasdfasdf",
            "latest_receipt_info": [
                {
                    "expires_date": "2020-07-27 00:02:39 Etc/GMT",
                    "expires_date_ms": "1595808159000",
                    "expires_date_pst": "2020-07-26 17:02:39 America/Los_Angeles",
                    "is_in_intro_offer_period": "false",
                    "is_trial_period": "false",
                    "original_purchase_date": "2020-06-27 00:02:42 Etc/GMT",
                    "original_purchase_date_ms": "1593216162000",
                    "original_purchase_date_pst": "2020-06-26 17:02:42 America/Los_Angeles",
                    "original_transaction_id": "000000000000000",
                    "product_id": "com.educreations.proteacher.1month",
                    "purchase_date": "2020-06-27 00:02:39 Etc/GMT",
                    "purchase_date_ms": "1593216159000",
                    "purchase_date_pst": "2020-06-26 17:02:39 America/Los_Angeles",
                    "quantity": "1",
                    "subscription_group_identifier": "00000000",
                    "transaction_id": "000000000000000",
                    "web_order_line_item_id": "000000000000000",
                }
            ],
            "pending_renewal_info": [
                {
                    "auto_renew_product_id": "com.educreations.proteacher.1month",
                    "auto_renew_status": "1",
                    "original_transaction_id": "000000000000000",
                    "product_id": "com.educreations.proteacher.1month",
                }
            ],
            "status": 0,
        },
    }

    form = AppleStatusUpdateForm(data)
    assert form.is_valid(), form.errors.as_data()


def test_apple_status_update_form_failed_to_renew():
    data = {
        "auto_renew_product_id": "com.educreations.proteacher.1month",
        "auto_renew_status": "true",
        "bid": "com.educreations.ios.Educreations",
        "bvrs": "00000",
        "environment": "PROD",
        "latest_receipt": "asdfasdf",
        "latest_expired_receipt_info": {
            "app_item_id": "000000000",
            "bid": "com.educreations.ios.Educreations",
            "bvrs": "00000",
            "expires_date": "1599527817000",
            "expires_date_formatted": "2020-09-08 01:16:57 Etc/GMT",
            "expires_date_formatted_pst": "2020-09-07 18:16:57 America/Los_Angeles",
            "is_in_intro_offer_period": "false",
            "is_trial_period": "false",
            "item_id": "000000000",
            "original_purchase_date": "2020-04-08 01:16:58 Etc/GMT",
            "original_purchase_date_ms": "1586308618000",
            "original_purchase_date_pst": "2020-04-07 18:16:58 America/Los_Angeles",
            "original_transaction_id": "70000762954330",
            "product_id": "com.educreations.proteacher.1month",
            "purchase_date": "2020-08-08 01:16:57 Etc/GMT",
            "purchase_date_ms": "1596849417000",
            "purchase_date_pst": "2020-08-07 18:16:57 America/Los_Angeles",
            "quantity": "1",
            "subscription_group_identifier": "00000000",
            "transaction_id": "00000000000000",
            "unique_identifier": "0000000000000000000000000000000000000000",
            "unique_vendor_identifier": "00000000-2AC8-44B0-89AB-EB057BAF7913",
            "version_external_identifier": "000000000",
            "web_order_line_item_id": "00000000000000",
        },
        "notification_type": "DID_FAIL_TO_RENEW",
        "password": "asdf",
        "unified_receipt": {
            "environment": "Production",
            "latest_receipt": "asdfasdfasdf",
        },
    }

    form = AppleStatusUpdateForm(data)
    assert form.is_valid(), form.errors.as_data()


def test_apple_status_update_form_non_subscription():
    data = {
        "bid": "com.educreations.ios.Educreations",
        "bvrs": "00000",
        "environment": "PROD",
        "latest_receipt": "asdfasdfasdf",
        "latest_receipt_info": {
            "app_item_id": "000000000",
            "bid": "com.educreations.ios.Educreations",
            "bvrs": "00000",
            "cancellation_date": "2020-09-05 11:48:12 Etc/GMT",
            "cancellation_date_ms": "1599306492000",
            "cancellation_date_pst": "2020-09-05 04:48:12 America/Los_Angeles",
            "cancellation_reason": "0",
            "is_in_intro_offer_period": "false",
            "is_trial_period": "false",
            "item_id": "000000000",
            "original_purchase_date": "2020-08-25 14:32:42 Etc/GMT",
            "original_purchase_date_ms": "1598365962000",
            "original_purchase_date_pst": "2020-08-25 07:32:42 America/Los_Angeles",
            "original_transaction_id": "00000000000000",
            "product_id": "com.educreations.proteacher.1year",
            "purchase_date": "2020-08-25 14:32:42 Etc/GMT",
            "purchase_date_ms": "1598365962000",
            "purchase_date_pst": "2020-08-25 07:32:42 America/Los_Angeles",
            "quantity": "1",
            "transaction_id": "00000000000000",
            "unique_identifier": "0000000000000000000000000000000000000000",
            "unique_vendor_identifier": "00000000-8B53-473C-9093-340CB76F2D26",
            "version_external_identifier": "000000000",
        },
        "notification_type": "REFUND",
        "password": "asdfasdf",
        "unified_receipt": {
            "environment": "Production",
            "latest_receipt": "asdfasdfasd",
        },
    }

    form = AppleStatusUpdateForm(data)
    assert form.is_valid(), form.errors.as_data()

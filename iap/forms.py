import base64
import datetime
import json
import logging

from django import forms
import pytz

from .widgets import IAPNullBooleanSelect

log = logging.getLogger(__name__)


EXPIRATION_INTENT_CHOICES = [
    (1, "Voluntary cancellation"),
    (2, "Billing error"),
    (3, "Declined price change"),
    (4, "Product not available at renewal"),
    (5, "Unknown error"),
]


def _clean_date(data, name, required=True):
    # Try to get the value in ms
    for key in (name + "_ms", name):
        if key not in data:
            continue

        value = data.get(key)

        # the date in ms
        seconds = int(value) / 1000.0
        return datetime.datetime.fromtimestamp(seconds, tz=pytz.utc)

    if required:
        raise forms.ValidationError("Unable to find a date for {}".format(name))

    return None


def _clean_base64_receipt(name, value):
    if not value:
        return None

    try:
        # Ensure the receipt can be base64 decoded
        return base64.b64decode(value)
    except TypeError:
        raise forms.ValidationError("Unable to base64 decode {}".format(name))


def _parse_json(name, value):
    # The following is to support py2 and py3
    # https://stackoverflow.com/a/22679982
    try:
        basestring  # noqa
    except NameError:
        basestring = (str, bytes)

    # Is this already decoded?
    if isinstance(value, basestring):
        # Decode the json value
        try:
            return json.loads(value)
        except ValueError as e:
            raise forms.ValidationError("Unable to JSON parse {}: {}".format(name, e))
    else:
        return value


def _clean_form_data(form_cls, name, value):
    if not value:
        return None

    loaded = _parse_json(name, value)

    if isinstance(loaded, list):
        log.warn(
            "Unable to parse form data for {} and field {}".format(
                form_cls.__name__, name
            )
        )
        raise forms.ValidationError("Unable to parse list {}: {}".format(name, loaded))

    log.info(
        "Parsed form data for {}".format(form_cls.__name__),
        extra={"data": {"value": value, "loaded": loaded}},
    )

    # Try to decode some of things in the json
    form = form_cls(loaded)
    if not form.is_valid():
        raise forms.ValidationError(
            "Unable to parse {}: {}".format(name, form.errors.as_data())
        )
    return form.cleaned_data


def _clean_list_of_form_data(form_cls, name, value):
    if not value:
        return None

    loaded = _parse_json(name, value)

    log.info("Cleaning form data list", extra={"data": {}})

    if not isinstance(loaded, list):
        raise forms.ValidationError(
            "Unable to parse non list {}: {}".format(name, loaded)
        )

    return [
        _clean_form_data(form_cls, "{}[{}]".format(name, i), item)
        for i, item in enumerate(loaded)
    ]


class AppleLatestReceiptInfoForm(forms.Form):
    """
    A Django form to validate receipt info

    See https://developer.apple.com/documentation/appstoreservernotifications/responsebody/latest_receipt_info
    """

    # An identifier that App Store Connect generates and the App Store uses to uniquely
    # identify the app purchased. Treat this value as a 64-bit integer.
    app_item_id = forms.IntegerField()

    # An identifier that App Store Connect generates and the App Store uses to uniquely
    # identify the in-app product purchased. Treat this value as a 64-bit integer.
    item_id = forms.IntegerField()

    # The unique identifier of the product purchased. You provide this value when
    # creating the product in App Store Connect, and it corresponds to the
    # productIdentifier property of the SKPayment object stored in the transaction's
    # payment property.
    product_id = forms.CharField()

    # The time of the original app purchase. This value indicates the date of the
    # subscription's initial purchase. The original purchase date applies to all
    # product types and remains the same in all transactions for the same product
    # ID. This value corresponds to the original transaction's transactionDate
    # property in StoreKit.
    original_purchase_date = forms.Field()

    # The time the App Store charged the user's account for a subscription purchase
    # or renewal after a lapse.
    purchase_date = forms.Field()

    # The time a subscription expires or when it will renew. Note that this field is
    # called expires_date_ms in the receipt.
    expires_date = forms.Field(required=False)

    # The transaction identifier of the original purchase.
    # See https://developer.apple.com/documentation/appstorereceipts/original_transaction_id
    original_transaction_id = forms.CharField()

    # A unique identifier for a transaction such as a purchase, restore, or renewal.
    # See https://developer.apple.com/documentation/appstorereceipts/transaction_id for more information
    transaction_id = forms.CharField()

    # An indicator of whether an auto-renewable subscription is in the introductory
    # price period.
    # https://developer.apple.com/documentation/appstorereceipts/is_in_intro_offer_period
    is_in_intro_offer_period = forms.NullBooleanField(widget=IAPNullBooleanSelect)

    # An indicator of whether a subscription is in the free trial period.
    # https://developer.apple.com/documentation/appstorereceipts/is_trial_period
    is_trial_period = forms.NullBooleanField(widget=IAPNullBooleanSelect)

    # The number of consumable products purchased. This value corresponds to the
    # quantity property of the SKPayment object stored in the transaction's payment
    # property. The value is usually "1" unless modified with a mutable payment.
    # The maximum value is "10".
    quantity = forms.IntegerField()

    # A unique identifier for purchase events across devices, including subscription-renewal
    # events. This value is the primary key for identifying subscription purchases.
    web_order_line_item_id = forms.CharField(required=False)

    def clean_original_purchase_date(self):
        return _clean_date(self.data, "original_purchase_date")

    def clean_purchase_date(self):
        return _clean_date(self.data, "purchase_date")

    def clean_expires_date(self):
        return _clean_date(self.data, "expires_date", required=False)


class AppleUnifiedLatestReceiptInfoForm(forms.Form):
    """
    A Django form to validate receipt info

    See https://developer.apple.com/documentation/appstorereceipts/responsebody/latest_receipt_info
    """

    CANCELLATION_REASON_CHOICES = ((0, "Other"), (1, "Issue"))

    # The time Apple customer support canceled a transaction, or the time an
    # auto-renewable subscription plan was upgraded. This field is only present
    # for refunded transactions.
    cancellation_date = forms.Field(required=False)

    # The reason for a refunded transaction. When a customer cancels a transaction,
    # the App Store gives them a refund and provides a value for this key. A value of
    # "1" indicates that the customer canceled their transaction due to an actual or
    # perceived issue within your app. A value of "0" indicates that the transaction
    # was canceled for another reason; for example, if the customer made the purchase
    # accidentally.
    cancellation_reason = forms.ChoiceField(
        choices=CANCELLATION_REASON_CHOICES, required=False
    )

    # The time a subscription expires or when it will renew.
    expires_date = forms.Field(required=False)

    # An indicator of whether an auto-renewable subscription is in the introductory
    # price period.
    # https://developer.apple.com/documentation/appstorereceipts/is_in_intro_offer_period
    is_in_intro_offer_period = forms.NullBooleanField(widget=IAPNullBooleanSelect)

    # An indicator of whether a subscription is in the free trial period.
    # https://developer.apple.com/documentation/appstorereceipts/is_trial_period
    is_trial_period = forms.NullBooleanField(widget=IAPNullBooleanSelect)

    # An indicator that a subscription has been canceled due to an upgrade. This
    # field is only present for upgrade transactions.
    is_upgraded = forms.NullBooleanField(widget=IAPNullBooleanSelect)

    # The time of the original app purchase. This value indicates the date of the
    # subscription's initial purchase. The original purchase date applies to all
    # product types and remains the same in all transactions for the same product
    # ID. This value corresponds to the original transaction's transactionDate
    # property in StoreKit.
    original_purchase_date = forms.Field()

    # The transaction identifier of the original purchase.
    # See https://developer.apple.com/documentation/appstorereceipts/original_transaction_id
    original_transaction_id = forms.CharField()

    # The unique identifier of the product purchased. You provide this value when
    # creating the product in App Store Connect, and it corresponds to the
    # productIdentifier property of the SKPayment object stored in the transaction's
    # payment property.
    product_id = forms.CharField()

    # The identifier of the subscription offer redeemed by the user. See promotional_offer_id for more information.
    promotional_offer_id = forms.CharField(required=False)

    # For consumable, non-consumable, and non-renewing subscription products, the time
    # the App Store charged the user's account for a purchased or restored product. For
    # auto-renewable subscriptions, the time the App Store charged the user's account
    # for a subscription purchase or renewal after a lapse.
    purchase_date = forms.Field()

    # The number of consumable products purchased. This value corresponds to the
    # quantity property of the SKPayment object stored in the transaction's payment
    # property. The value is usually "1" unless modified with a mutable payment.
    # The maximum value is "10".
    quantity = forms.IntegerField()

    # The identifier of the subscription group to which the subscription belongs. The value for this field is identical to the subscriptionGroupIdentifier property in SKProduct.
    subscription_group_identifier = forms.CharField(required=False)

    # A unique identifier for a transaction such as a purchase, restore, or renewal.
    # See https://developer.apple.com/documentation/appstorereceipts/transaction_id for more information
    transaction_id = forms.CharField()

    # A unique identifier for purchase events across devices, including subscription-renewal
    # events. This value is the primary key for identifying subscription purchases.
    web_order_line_item_id = forms.CharField(required=False)

    def clean_cancellation_date(self):
        return _clean_date(self.data, "cancellation_date", required=False)

    def clean_original_purchase_date(self):
        return _clean_date(self.data, "original_purchase_date")

    def clean_purchase_date(self):
        return _clean_date(self.data, "purchase_date")

    def clean_expires_date(self):
        return _clean_date(self.data, "expires_date", required=False)


class AppleUnifiedPendingRenewalInfoForm(forms.Form):
    """
    A Django form to validate a pending renewal structure in a unified receipt structure.

    https://developer.apple.com/documentation/appstorereceipts/responsebody/pending_renewal_info
    """

    PRICE_CONSENT_CHOICES = ((0, "Pending"), (1, "Consented"))

    # The current renewal preference for the auto-renewable subscription. The value for this key
    # corresponds to the productIdentifier property of the product that the customer's subscription
    # renews. This field is only present if the user downgrades or crossgrades to a subscription of
    #   a different duration for the subsequent subscription period.
    auto_renew_product_id = forms.CharField(required=False)

    # The unique identifier of the product purchased. You provide this value when
    # creating the product in App Store Connect, and it corresponds to the
    # productIdentifier property of the SKPayment object stored in the transaction's
    # payment property.
    product_id = forms.CharField()

    # The current renewal status for an auto-renewable subscription product. Note
    # that these values are different from those of the auto_renew_status in the
    # receipt.
    # https://developer.apple.com/documentation/appstorereceipts/auto_renew_status
    auto_renew_status = forms.NullBooleanField(widget=IAPNullBooleanSelect)

    # The reason a subscription expired. This field is only present for an expired
    # auto-renewable subscription.
    expiration_intent = forms.ChoiceField(
        choices=EXPIRATION_INTENT_CHOICES, required=False
    )

    # The time at which the grace period for subscription renewals expires. This key
    # is only present for apps that have Billing Grace Period enabled and when the
    # user experiences a billing error at the time of renewal.
    grace_period_expires_date = forms.Field(required=False)

    # A flag that indicates Apple is attempting to renew an expired subscription
    # automatically. This field is only present if an auto-renewable subscription
    # is in the billing retry state.
    # https://developer.apple.com/documentation/appstorereceipts/is_in_billing_retry_period
    is_in_billing_retry_period = forms.NullBooleanField(widget=IAPNullBooleanSelect)

    # The transaction identifier of the original purchase.
    # See https://developer.apple.com/documentation/appstorereceipts/original_transaction_id
    original_transaction_id = forms.CharField()

    # The price consent status for a subscription price increase. This field is only present
    # if the customer was notified of the price increase. The default value is "0" and changes
    # to "1" if the customer consents.
    price_consent_status = forms.ChoiceField(
        choices=PRICE_CONSENT_CHOICES, required=False
    )

    def clean_grace_period_expires_date(self):
        return _clean_date(self.data, "grace_period_expires_date", required=False)


class AppleUnifiedReceiptForm(forms.Form):
    """
    A Django form to validate a unified reciept.

    https://developer.apple.com/documentation/appstoreservernotifications/unified_receipt
    """

    ENVIRONMENTS = ("Sandbox", "Production")
    ENVIRONMENT_CHOICES = [(env, env) for env in ENVIRONMENTS]

    # Specifies whether the notification is for a sandbox or a production
    # environment.
    environment = forms.ChoiceField(choices=ENVIRONMENT_CHOICES)

    # The latest Base64-encoded app receipt.
    latest_receipt = forms.CharField(required=False)

    # An array that contains the latest 100 in-app purchase transactions
    # of the decoded value in latest_receipt. This array excludes
    # transactions for consumable products that your app has marked
    # as finished. The contents of this array are identical to those
    # in responseBody.Latest_receipt_info in the verifyReceipt endpoint
    # response for receipt validation.
    latest_receipt_info = forms.Field(required=False)

    # An array where each element contains the pending renewal information
    # for each auto-renewable subscription identified in product_id. The
    # contents of this array are identical to those in
    # responseBody.Pending_renewal_info in the verifyReciept endpoint
    # response for receipt validation.
    pending_renewal_info = forms.Field(required=False)

    # The status code, where 0 indicates that the notification is valid.
    status = forms.IntegerField(required=False)

    def clean_status(self):
        value = self.cleaned_data["status"]
        value = 0 if value is None else value
        if value != 0:
            raise forms.ValidationError(
                "Invalid unified receipt status: {}".format(value)
            )
        return value

    def clean_latest_receipt(self):
        return _clean_base64_receipt(
            "latest_receipt", self.cleaned_data.get("latest_receipt")
        )

    def clean_latest_receipt_info(self):
        return _clean_list_of_form_data(
            AppleUnifiedLatestReceiptInfoForm,
            "latest_receipt_info",
            self.cleaned_data.get("latest_receipt_info"),
        )

    def clean_pending_renewal_info(self):
        return _clean_list_of_form_data(
            AppleUnifiedPendingRenewalInfoForm,
            "pending_renewal_info",
            self.cleaned_data.get("pending_renewal_info"),
        )


class AppleStatusUpdateForm(forms.Form):
    """
    A Django form to validate the POST sent by Apple on subscription updates.

    See https://developer.apple.com/documentation/storekit/in-app_purchase/enabling_status_update_notifications  # noqa
    See https://developer.apple.com/documentation/appstoreservernotifications
    """

    ENVIRONMENTS = ("Sandbox", "PROD")
    ENVIRONMENT_CHOICES = [
        (ENVIRONMENTS[0], "Sandbox"),
        [ENVIRONMENTS[1], "Production"],
    ]

    INITIAL_BUY = "INITIAL_BUY"
    CANCEL = "CANCEL"
    INTERACTIVE_RENEWAL = "INTERACTIVE_RENEWAL"
    DID_CHANGE_RENEWAL_PREF = "DID_CHANGE_RENEWAL_PREF"
    DID_CHANGE_RENEWAL_STATUS = "DID_CHANGE_RENEWAL_STATUS"
    DID_FAIL_TO_RENEW = "DID_FAIL_TO_RENEW"
    DID_RECOVER = "DID_RECOVER"
    REFUND = "REFUND"

    # Deprecated, use DID_RECOVER instead
    RENEWAL = "RENEWAL"

    NOTIFICATION_TYPES = (
        INITIAL_BUY,
        CANCEL,
        INTERACTIVE_RENEWAL,
        DID_CHANGE_RENEWAL_PREF,
        DID_CHANGE_RENEWAL_STATUS,
        DID_FAIL_TO_RENEW,
        DID_RECOVER,
        REFUND,
        # Deprecated
        RENEWAL,
    )

    NOTIFICATION_CHOICES = [
        (notif, notif.replace("_", " ").title()) for notif in NOTIFICATION_TYPES
    ]

    # Specifies whether the notification is for a sandbox or a production
    # environment.
    environment = forms.ChoiceField(choices=ENVIRONMENT_CHOICES)

    # The subscription event that triggered the notification.
    notification_type = forms.ChoiceField(choices=NOTIFICATION_CHOICES)

    # The same value as the shared secret you submit in the password field
    # of the requestBody when validating receipts.
    password = forms.CharField()

    # A string that contains the app bundle ID.
    bid = forms.CharField()

    # A string that contains the app bundle version.
    bvrs = forms.CharField()

    # An identifier that App Store Connect generates and the App Store uses to
    # uniquely identify the auto-renewable subscription that the user's
    # subscription renews. Treat this value as a 64-bit integer.
    # TODO(streeter) - convert to an integer?
    auto_renew_adam_id = forms.CharField(required=False, max_length=64)

    # The product identifier of the auto-renewable subscription that the user's
    # subscription renews.
    auto_renew_product_id = forms.CharField(required=False)

    # The current renewal status for an auto-renewable subscription product. Note
    # that these values are different from those of the auto_renew_status in the
    # receipt.
    auto_renew_status = forms.NullBooleanField(widget=IAPNullBooleanSelect)

    # The time at which the renewal status for an auto-renewable subscription was
    # turned on or off.
    auto_renew_status_change_date = forms.Field(required=False)

    # The reason a subscription expired. This field is only present for an expired
    # auto-renewable subscription.
    expiration_intent = forms.ChoiceField(
        choices=EXPIRATION_INTENT_CHOICES, required=False
    )

    # The latest Base64-encoded transaction receipt. This field appears in the
    # notification instead of latest_receipt for expired transactions.
    latest_expired_receipt = forms.CharField(required=False)

    # The JSON representation of the value in latest_expired_receipt. This appears
    # in the notification instead of latest_receipt_info for expired transactions.
    latest_expired_receipt_info = forms.Field(required=False)

    # The latest Base64-encoded transaction receipt.
    latest_receipt = forms.CharField(required=False)

    # The JSON representation of the value in latest_receipt. Note that this
    # field is an array in the receipt but a single object in server-to-server
    # notifications. Not sent for expired transactions.
    latest_receipt_info = forms.Field(required=False)

    # An object that contains information about the most recent in-app purchase
    # transactions for the app.
    unified_receipt = forms.Field(required=False)

    def clean_auto_renew_status_change_date(self):
        return _clean_date(self.data, "auto_renew_status_change_date", required=False)

    def clean_latest_receipt(self):
        return _clean_base64_receipt(
            "latest_receipt", self.cleaned_data.get("latest_receipt")
        )

    def clean_latest_receipt_info(self):
        return _clean_form_data(
            AppleLatestReceiptInfoForm,
            "latest_receipt_info",
            self.cleaned_data.get("latest_receipt_info"),
        )

    def clean_latest_expired_receipt(self):
        return _clean_base64_receipt(
            "latest_expired_receipt", self.cleaned_data.get("latest_expired_receipt")
        )

    def clean_latest_expired_receipt_info(self):
        return _clean_form_data(
            AppleLatestReceiptInfoForm,
            "latest_receipt_info",
            self.cleaned_data.get("latest_receipt_info"),
        )

    def clean_unified_receipt(self):
        return _clean_form_data(
            AppleUnifiedReceiptForm,
            "unified_receipt",
            self.cleaned_data.get("unified_receipt"),
        )

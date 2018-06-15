import json

from django import forms


class AppleStatusUpdateForm(forms.Form):
    """
    A Django form to validate the POST sent by Apple on subscription updates.

    See https://developer.apple.com/library/archive/documentation/NetworkingInternet/Conceptual/StoreKitGuide/Chapters/Subscriptions.html#//apple_ref/doc/uid/TP40008267-CH7-SW13
    """

    ENVIRONMENTS = ('Sandbox', 'PROD')

    INITIAL_BUY = 'INITIAL_BUY'
    CANCEL = 'CANCEL'
    RENEW = 'RENEW'
    INTERACTIVE_RENEWAL = 'INTERACTIVE_RENEWAL'
    DID_CHANGE_RENEWAL_PREF = 'DID_CHANGE_RENEWAL_PREF'

    NOTIFICATION_TYPES = (
        INITIAL_BUY,
        CANCEL,
        RENEW,
        INTERACTIVE_RENEWAL,
        DID_CHANGE_RENEWAL_PREF,
    )

    # Specifies whether the notification is for a sandbox or a production
    # environment.
    environment = forms.ChoiceField(choices=[
        (env.lower(), env) for env in ENVIRONMENTS
    ])

    # Describes the kind of event that triggered the notification.
    notification_type = forms.ChoiceField(choices=[
        (notif.lower(), notif) for notif in NOTIFICATION_TYPES
    ])

    # This value is the same as the shared secret you POST when validating
    # receipts.
    password = forms.CharField()

    # This value is the same as the Original Transaction Identifier in the
    # receipt. You can use this value to relate multiple iOS 6-style transaction
    # receipts for an individual customer’s subscription.
    original_transaction_id = forms.CharField()

    # The time and date that a transaction was cancelled by Apple customer
    # support. Posted only if the notification_type is CANCEL.
    cancellation_date = forms.CharField(required=False)

    # The primary key for identifying a subscription purchase. Posted only if
    # the notification_type is CANCEL.
    web_order_line_item_id = forms.CharField(required=False)

    # The base-64 encoded transaction receipt for the most recent renewal
    # transaction. Posted only if the notification_type is RENEWAL or
    # INTERACTIVE_RENEWAL, and only if the renewal is successful.
    latest_receipt = forms.FileField(required=False)

    # The JSON representation of the receipt for the most recent renewal.
    # Posted only if renewal is successful. Not posted for notification_type
    # CANCEL.
    latest_receipt_info = forms.CharField(required=False)

    # The base-64 encoded transaction receipt for the most recent renewal
    # transaction. Posted only if the subscription expired.
    latest_expired_receipt = forms.FileField(required=False)

    # The JSON representation of the receipt for the most recent renewal
    # transaction. Posted only if the notification_type is RENEWAL or CANCEL or
    # if renewal failed and subscription expired.
    latest_expired_receipt_info = forms.CharField(required=False)

    # A Boolean value indicated by strings “true” or “false”. This is the same
    # as the auto renew status in the receipt.
    auto_renew_status = forms.NullBooleanField()

    # The current renewal preference for the auto-renewable subscription. This
    # is the Apple ID of the product.
    auto_renew_adam_id = forms.CharField(required=False)

    # This is the same as the Subscription Auto Renew Preference in the receipt.
    auto_renew_product_id = forms.CharField(required=False)

    # This is the same as the Subscription Expiration Intent in the receipt.
    # Posted only if notification_type is RENEWAL or INTERACTIVE_RENEWAL.
    expiration_intent = forms.CharField(required=False)

    def clean_latest_receipt_info(self):
        info = self.cleaned_data.get('latest_receipt_info')
        if info is None:
            return info

        try:
            return json.loads(info)
        except ValueError:
            raise forms.ValidationError('Unable to parse latest_receipt_info')

    def clean_latest_expired_receipt_info(self):
        info = self.cleaned_data.get('latest_expired_receipt_info')
        if info is None:
            return info

        try:
            return json.loads(info)
        except ValueError:
            raise forms.ValidationError('Unable to parse latest_expired_receipt_info')

import base64
import json

from django import forms


class AppleStatusUpdateForm(forms.Form):
    """
    A Django form to validate the POST sent by Apple on subscription updates.

    See https://developer.apple.com/documentation/storekit/in-app_purchase/enabling_status_update_notifications
    """

    ENVIRONMENTS = ('Sandbox', 'PROD')

    INITIAL_BUY = 'INITIAL_BUY'
    CANCEL = 'CANCEL'
    RENEWAL = 'RENEWAL'
    INTERACTIVE_RENEWAL = 'INTERACTIVE_RENEWAL'
    DID_CHANGE_RENEWAL_PREF = 'DID_CHANGE_RENEWAL_PREF'
    DID_CHANGE_RENEWAL_STATUS = 'DID_CHANGE_RENEWAL_STATUS'

    NOTIFICATION_TYPES = (
        INITIAL_BUY,
        CANCEL,
        RENEWAL,
        INTERACTIVE_RENEWAL,
        DID_CHANGE_RENEWAL_PREF,
        DID_CHANGE_RENEWAL_STATUS,
    )

    # Specifies whether the notification is for a sandbox or a production
    # environment.
    environment = forms.ChoiceField(choices=[
        (env, env.lower()) for env in ENVIRONMENTS
    ])

    # Describes the kind of event that triggered the notification.
    notification_type = forms.ChoiceField(choices=[
        (notif, notif.lower()) for notif in NOTIFICATION_TYPES
    ])

    # This value is the same as the shared secret you POST when validating
    # receipts.
    password = forms.CharField()

    # This value is the same as the Original Transaction Identifier in the
    # receipt. You can use this value to relate multiple iOS 6-style transaction
    # receipts for an individual customer's subscription.
    original_transaction_id = forms.CharField(required=False)

    # The time and date that a transaction was cancelled by Apple customer
    # support. Posted only if the notification_type is CANCEL.
    cancellation_date = forms.CharField(required=False)

    # The primary key for identifying a subscription purchase. Posted only if
    # the notification_type is CANCEL.
    web_order_line_item_id = forms.CharField(required=False)

    # The base-64 encoded transaction receipt for the most recent renewal
    # transaction. Posted only if the notification_type is RENEWAL or
    # INTERACTIVE_RENEWAL, and only if the renewal is successful.
    latest_receipt = forms.CharField(required=False)

    # The JSON representation of the receipt for the most recent renewal.
    # Posted only if renewal is successful. Not posted for notification_type
    # CANCEL.
    latest_receipt_info = forms.Field(required=False)

    # The base-64 encoded transaction receipt for the most recent renewal
    # transaction. Posted only if the subscription expired.
    latest_expired_receipt = forms.CharField(required=False)

    # The JSON representation of the receipt for the most recent renewal
    # transaction. Posted only if the notification_type is RENEWAL or CANCEL or
    # if renewal failed and subscription expired.
    latest_expired_receipt_info = forms.Field(required=False)

    # A Boolean value indicated by strings "true" or "false". This is the same
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

    def _clean_receipt(self, name):
        receipt = self.cleaned_data.get(name)
        if not receipt:
            return None

        try:
            # Ensure the receipt can be base 64 decoded
            base64.b64decode(receipt)
        except TypeError:
            raise forms.ValidationError('Unable to decode {}'.format(name))
        return receipt

    def _clean_receipt_info(self, name):
        info = self.cleaned_data.get(name)
        if not info:
            return None

        if not isinstance(info, basestring):
            return info

        try:
            return json.loads(info)
        except ValueError as e:
            raise forms.ValidationError(
                'Unable to parse {} "{}": {}'.format(name, info, e))

    def clean_latest_receipt(self):
        return self._clean_receipt('latest_receipt')

    def clean_latest_receipt_info(self):
        return self._clean_receipt_info('latest_receipt_info')

    def clean_latest_expired_receipt(self):
        return self._clean_receipt('latest_expired_receipt')

    def clean_latest_expired_receipt_info(self):
        return self._clean_receipt_info('latest_expired_receipt_info')

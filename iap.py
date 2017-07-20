import base64
import datetime
import json
import os
import subprocess

import requests
from Crypto.Util import asn1
from django.conf import settings

try:
    from simplejson.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

__all__ = [
    'InvalidReceipt',
    'NoActiveReceiptException',
    'NoPurchasesException',
    'ReceiptValidationException',
    'parse_receipt',
    'validate_debug_receipt',
    'validate_production_receipt',
    'validate_receipt_with_apple',
    'validate_receipt_is_active',
]

CA_FILE = settings.IAP_SETTINGS['CA_FILE']

IAP_SHARED_SECRET = settings.IAP_SETTINGS.get('SHARED_SECRET')

PRODUCTION_VERIFICATION_URL = 'https://buy.itunes.apple.com/verifyReceipt'
SANDBOX_VERIFICATION_URL = 'https://sandbox.itunes.apple.com/verifyReceipt'

PRODUCTION_BUNDLE_ID = settings.IAP_SETTINGS['PRODUCTION_BUNDLE_ID']
DEBUG_BUNDLE_ID = settings.IAP_SETTINGS.get('DEBUG_BUNDLE_ID')

PRODUCTION_PRODUCT_IDS = settings.IAP_SETTINGS.get(
    'PRODUCTION_PRODUCT_IDS', set())
DEBUG_PRODUCT_IDS = settings.IAP_SETTINGS.get(
    'DEBUG_PRODUCT_IDS', set())


class InvalidReceipt(Exception):
    pass


class ReceiptValidationException(Exception):
    def __init__(self, receipt, *args, **kwargs):
        self.receipt = receipt
        super(ReceiptValidationException, self).__init__(*args, **kwargs)


class RetryReceiptValidation(ReceiptValidationException):
    pass


class NoActiveReceiptException(ReceiptValidationException):
    pass


class NoPurchasesException(ReceiptValidationException):
    pass


def verify_receipt_sig(raw_data):
    proc = subprocess.Popen([
        'openssl', 'smime', '-verify',
        '-inform', 'der',
        '-CAfile', CA_FILE,
        '-binary',
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    signed_data, err_data = proc.communicate(raw_data)
    if proc.wait() != os.EX_OK:
        raise InvalidReceipt('Signature verification failed:\n' + err_data)
    return signed_data


def decode_obj(data, expected_type):
    der = asn1.DerObject()
    der.decode(data)
    if der.typeTag != expected_type:
        raise InvalidReceipt('Expected tag type {}; got {}'.format(
            expected_type, der.typeTag))
    return der.payload


def decode_seq_set(data):
    result = []
    offset = 0
    while offset < len(data):
        der = asn1.DerSequence()
        length = der.decode(data[offset:])
        offset += length
        result.append(list(der))
    return result


def decode_ia5(data):
    return decode_obj(data, 22).decode('ascii')


def decode_utf8(data):
    return decode_obj(data, 12).decode('utf-8')


def decode_int(data):
    der = asn1.DerInteger()
    der.decode(data)
    return der.value


def decode_receipt(data):
    # See https://developer.apple.com/library/ios/releasenotes/General/
    #   ValidateAppStoreReceipt/Chapters/ReceiptFields.html
    fields = {
        0: ('_environment', decode_utf8),
        2: ('bundle_id', decode_utf8),
        3: ('application_version', decode_utf8),
        # 4: ('_opaque_value', lambda x: x),
        # 5: ('_sha1_hash', lambda x: x),
        17: ('in_app', decode_receipt),
        19: ('original_application_version', decode_utf8),
        21: ('expiration_date', decode_ia5),
        1701: ('quantity', decode_int),
        1702: ('product_id', decode_utf8),
        1703: ('transaction_id', decode_utf8),
        1704: ('purchase_date', decode_ia5),
        1705: ('original_transaction_id', decode_utf8),
        1706: ('original_purchase_date', decode_ia5),
        1708: ('expires_date', decode_ia5),
        1711: ('web_order_line_item_id', decode_int),
        1712: ('cancellation_date', decode_ia5),
    }
    list_fields = [17]

    payload = decode_obj(data, 49)
    result = {}
    for attr_type, attr_version, attr_raw_value in decode_seq_set(payload):
        attr_value = decode_obj(attr_raw_value, 4)

        name, decoder = fields.get(attr_type, (None, None))
        if attr_type in list_fields:
            result.setdefault(name, []).append(decoder(attr_value))
        elif name is not None:
            result[name] = decoder(attr_value)
        # else:
        #    result['_unknown_{}'.format(attr_type)] = attr_value

    result['_sandbox'] = (
        result.get('original_application_version') == '1.0' and
        result.get('_environment') != 'Production')

    return result


def parse_receipt(raw_data):
    return decode_receipt(verify_receipt_sig(raw_data))


def validate_receipt_with_apple(data):
    payload = {'receipt-data': base64.b64encode(data)}

    if IAP_SHARED_SECRET:
        payload['password'] = IAP_SHARED_SECRET

    # Docs at http://goo.gl/WV5U63
    for url in (PRODUCTION_VERIFICATION_URL, SANDBOX_VERIFICATION_URL):
        r = requests.post(url, data=json.dumps(payload))
        r.raise_for_status()
        try:
            content = r.json()
        except JSONDecodeError:
            raise ReceiptValidationException({}, 'Unable to read response')

        if 'status' not in content:
            raise ReceiptValidationException(content, 'Unknown response format')
        status = content.get('status', 21000)
        if status == 21000:
            # The App Store could not read the JSON object you provided.
            raise ReceiptValidationException(content, 'Unable to read payload')
        elif status == 21002:
            # The data in the receipt-data property was malformed or missing.
            raise ReceiptValidationException(content, 'Malformed receipt-data')
        elif status == 21003:
            # The receipt could not be authenticated.
            raise ReceiptValidationException(
                content, 'Receipt is from an unknown source')
        elif status == 21004:
            # Bad shared secret for the app / auth failed
            # NOTE: Only returned for iOS 6 style transaction receipts for
            # auto-renewable subscriptions.
            raise ReceiptValidationException(
                content, 'The shared secret does not match one on file')
        elif status == 21005:
            # The receipt server is not currently available.
            raise ReceiptValidationException(content, 'WebObjects')
        elif status == 21006:
            # The receipt is inactive
            # NOTE: Only returned for iOS 6 style transaction receipts for
            # auto-renewable subscriptions. For iOS 7 style app receipts, the
            # status code is reflects the status of the app receipt as a whole.
            # For example, if you send a valid app receipt that contains an
            # expired subscription, the response is 0 because the receipt as a
            # whole is valid.
            raise ReceiptValidationException(content, 'Inactive subscription')
        elif status == 21007:
            if url == PRODUCTION_VERIFICATION_URL:
                # We need to try the other environment
                continue
            raise ReceiptValidationException(content, 'Cannot try another url!')
        elif status == 21008:
            raise ReceiptValidationException(content, 'We already tried prod!')
        elif status == 21009:
            # This seems to be an internal Apple error. In this case,
            # one should retry the request
            raise RetryReceiptValidation(content, 'Internal Apple error. Retry')
        elif status == 21010:
            # This receipt could not be authorized. Treated as if the purchase
            # was never made.
            raise NoPurchasesException(
                    content, 'The receipt could not be authorized')
        elif status != 0:
            raise RetryReceiptValidation(
                content, 'Unknown status code %s. Retry' % status)

        if 'receipt' not in content:
            raise ReceiptValidationException(
                content, 'Unable to get receipt from Apple')

        receipt = content.get('receipt', [])
        if not len(receipt):
            raise ReceiptValidationException(content, 'Not enough receipt!')

        in_app_purchases = receipt.get('in_app', [])
        if not len(in_app_purchases):
            raise NoPurchasesException(content, 'No IAPs for receipt!')

        latest_receipt = receipt.get('latest_receipt')
        if latest_receipt:
            try:
                receipt['latest_receipt_encoded'] = latest_receipt
                receipt['latest_receipt'] = base64.b64decode(latest_receipt)
            except TypeError:
                raise ReceiptValidationException(
                    content, 'Cannot decode latest_receipt')

        return content


def validate_device(decoded_receipt, bundle_ids):
    if 'bundle_id' not in decoded_receipt:
        raise InvalidReceipt(u'Unknown decoded receipt format!')
    if decoded_receipt['bundle_id'] not in bundle_ids:
        raise InvalidReceipt(
            u'Unexpected bundle_id in decoded receipt {}'.format(
                decoded_receipt['bundle_id']))
    return True


def validate_product(decoded_receipt, product_ids):
    # If there are no products in the receipt, they are all ok
    for in_app in decoded_receipt.get('in_app', []):
        if 'product_id' not in in_app:
            raise InvalidReceipt(u'Unknown decoded receipt format!')
        if in_app['product_id'] not in product_ids:
            raise InvalidReceipt(
                u'Unexpected product_id in decoded receipt {}'.format(
                    in_app['product_id']))
    return True


def validate_production_receipt(decoded_receipt):
    validate_device(decoded_receipt, [PRODUCTION_BUNDLE_ID])
    validate_product(decoded_receipt, PRODUCTION_PRODUCT_IDS)


def validate_debug_receipt(decoded_receipt):
    if not decoded_receipt.get('_sandbox', False):
        raise InvalidReceipt('Debug receipts must be in the sandbox!')

    bundle_ids = ([DEBUG_BUNDLE_ID, PRODUCTION_BUNDLE_ID]
                  if DEBUG_BUNDLE_ID else [PRODUCTION_BUNDLE_ID])

    # The sandbox can have both production and debug bundle and product ids.
    # This is because when the app is in review, they test on the sandbox,
    # but are using a production build of the app.
    validate_device(decoded_receipt, bundle_ids)
    validate_product(
        decoded_receipt, DEBUG_PRODUCT_IDS | PRODUCTION_PRODUCT_IDS)


def validate_receipt_is_active(data, timedelta, is_test=False):
    # Establish grace period
    delta_kwargs = {'minutes': 1} if is_test else {'days': 1}
    grace_period = datetime.timedelta(**delta_kwargs)

    # Check with Apple
    try:
        updated_content = validate_receipt_with_apple(data)
    except RetryReceiptValidation:
        # Try one more time
        updated_content = validate_receipt_with_apple(data)

    # Validate the device and product are ok
    local_validation = (
        validate_debug_receipt if is_test else validate_production_receipt)
    local_validation(updated_content['receipt'])

    # Use the latest receipt information from Apple, otherwise
    # use the IAP from the receipt. latest_receipt_info is only returned for
    # iOS 6 style transaction receipts for auto-renewable subscriptions.
    # From Apple:
    #
    # The values of the latest_receipt and latest_receipt_info keys are useful
    # when checking whether an auto-renewable subscription is currently active.
    # By providing any transaction receipt for the subscription and checking
    # these values, you can get information about the currently-active
    # subscription period. If the receipt being validated is for the latest
    # renewal, the value for latest_receipt is the same as receipt-data
    # (in the request) and the value for latest_receipt_info is the same as
    # receipt.
    iaps = updated_content.get(
        'latest_receipt_info', updated_content['receipt']['in_app'])

    # Ensure the updated receipt has an active subscription.
    for iap in iaps:
        if iap.get('cancellation_date'):
            # This iap is canceled. Ignore it
            continue
        # Look for an expires_date
        expires_date_ms = int(iap.get('expires_date_ms', 0))
        if expires_date_ms:
            # See if this iap is expired
            expires_date_sec = expires_date_ms / 1000.0
            expires_date = datetime.datetime.utcfromtimestamp(expires_date_sec)
            if datetime.datetime.utcnow() < expires_date + grace_period:
                return
        else:
            # Check the subscription period
            purchase_date_sec = int(iap['original_purchase_date_ms']) / 1000.0
            purchase_date = datetime.datetime.utcfromtimestamp(
                purchase_date_sec)
            expires_date = purchase_date + timedelta
            if datetime.datetime.utcnow() < expires_date + grace_period:
                return
    raise NoActiveReceiptException(
        updated_content, 'No active IAP was found in the receipt')

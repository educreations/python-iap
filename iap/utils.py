import base64
import datetime
import json

from cffi import FFI
from OpenSSL import crypto
from pyasn1_modules import rfc2315
from pyasn1.codec.der import decoder
from pyasn1.type import namedtype, namedval, univ, char
import requests

try:
    from simplejson.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

from .exceptions import (
    InvalidReceipt,
    NoActiveReceiptException,
    NoPurchasesException,
    ReceiptValidationException,
    RetryReceiptValidation,
)

from .settings import (
    CA_FILE,
    IAP_SHARED_SECRET,
    PRODUCTION_VERIFICATION_URL,
    SANDBOX_VERIFICATION_URL,
    PRODUCTION_BUNDLE_ID,
    DEBUG_BUNDLE_ID,
    PRODUCTION_PRODUCT_IDS,
    DEBUG_PRODUCT_IDS,
)

ffi = FFI()


def load_pkcs7_bio_der(p7_der):
    """
    Load a PKCS7 object from a PKCS7 DER blob.
    Return PKCS7 object.
    """
    try:
        return crypto.load_pkcs7_data(crypto.FILETYPE_ASN1, p7_der)
    except crypto.Error as ex:
        raise InvalidReceipt('Unable to load PCKS7 data')


def verify_receipt_sig(raw_data):
    store = crypto.X509Store()

    with open(CA_FILE, 'rb') as ca_cert_file:
        ca_cert_string = ca_cert_file.read()

    cert = crypto.load_certificate(crypto.FILETYPE_PEM, ca_cert_string)

    store.add_cert(cert)

    p7 = load_pkcs7_bio_der(raw_data)
    out = crypto._new_mem_buf()
    if not crypto._lib.PKCS7_verify(
            p7._pkcs7, ffi.NULL, store._store, ffi.NULL, out, 0):
        raise InvalidReceipt('Signature verification failed')

    return crypto._bio_to_string(out)


TYPE_ENVIRONMENT = 0
TYPE_BUNDLE_ID = 2
TYPE_APPLICATION_VERSION = 3
TYPE_OPAQUE_VALUE = 4
TYPE_SHA1_HASH = 5
TYPE_RECEIPT_CREATION_DATE = 12
TYPE_IN_APP = 17
TYPE_ORIGINAL_PURCHASE_DATE = 18
TYPE_ORIGINAL_APPLICATION_VERSION = 19
TYPE_EXPIRATION_DATE = 21

TYPE_IN_APP_QUANTITY = 1701
TYPE_IN_APP_PRODUCT_ID = 1702
TYPE_IN_APP_TRANSACTION_ID = 1703
TYPE_IN_APP_PURCHASE_DATE = 1704
TYPE_IN_APP_ORIGINAL_TRANSACTION_ID = 1705
TYPE_IN_APP_ORIGINAL_PURCHASE_DATE = 1706
TYPE_IN_APP_EXPIRES_DATE = 1708
TYPE_IN_APP_WEB_ORDER_LINE_ITEM_ID = 1711
TYPE_IN_APP_CANCELLATION_DATE = 1712


def decode_ia5(data):
    ia5_str, _ = decoder.decode(data, asn1Spec=char.IA5String())

    return str(ia5_str)


def decode_utf8(data):
    s, _ = decoder.decode(data, asn1Spec=char.UTF8String())
    return str(s)


def decode_int(data):
    i, _ = decoder.decode(data, asn1Spec=univ.Integer())
    return int(i)


# See https://developer.apple.com/library/ios/releasenotes/General/ValidateAppStoreReceipt/Chapters/ReceiptFields.html
RECEIPT_FIELD_MAP = {
    TYPE_ENVIRONMENT: decode_utf8,
    TYPE_BUNDLE_ID: decode_utf8,
    TYPE_APPLICATION_VERSION: decode_utf8,
    TYPE_OPAQUE_VALUE: (lambda x: x.asOctets()),
    TYPE_SHA1_HASH: (lambda x: x.asOctets()),
    TYPE_RECEIPT_CREATION_DATE: decode_ia5,
    TYPE_ORIGINAL_PURCHASE_DATE: decode_ia5,
    TYPE_ORIGINAL_APPLICATION_VERSION: decode_utf8,
    TYPE_EXPIRATION_DATE: decode_ia5,
}

IN_APP_FIELD_MAP = {
    TYPE_IN_APP_QUANTITY: decode_int,
    TYPE_IN_APP_PRODUCT_ID: decode_utf8,
    TYPE_IN_APP_TRANSACTION_ID: decode_utf8,
    TYPE_IN_APP_PURCHASE_DATE: decode_ia5,
    TYPE_IN_APP_ORIGINAL_TRANSACTION_ID: decode_utf8,
    TYPE_IN_APP_ORIGINAL_PURCHASE_DATE: decode_ia5,
    TYPE_IN_APP_EXPIRES_DATE: decode_ia5,
    TYPE_IN_APP_WEB_ORDER_LINE_ITEM_ID: decode_int,
    TYPE_IN_APP_CANCELLATION_DATE: decode_ia5,
}


class FieldMap:
    def __init__(self, field_map):
        self.field_map = field_map

    def convert(self, from_type, from_value):
        return self.field_map.get(from_type, lambda x: x)(from_value)


class AppReceiptFieldType(univ.Integer):
    """Apple App Receipt named field type"""

    namedValues = namedval.NamedValues(
        ('_environment', TYPE_ENVIRONMENT),
        ('bundle_id', TYPE_BUNDLE_ID),
        ('application_version', TYPE_APPLICATION_VERSION),
        ('_opaque_value', TYPE_OPAQUE_VALUE),
        ('_sha1_hash', TYPE_SHA1_HASH),
        ('creation_date', TYPE_RECEIPT_CREATION_DATE),
        ('in_app', TYPE_IN_APP),
        ('original_purchase_date', TYPE_ORIGINAL_PURCHASE_DATE),
        ('original_application_version', TYPE_ORIGINAL_APPLICATION_VERSION),
        ('expiration_date', TYPE_EXPIRATION_DATE),
    )


class AppReceiptField(univ.Sequence):
    """Apple App Receipt field"""

    componentType = namedtype.NamedTypes(
        namedtype.NamedType('type', AppReceiptFieldType()),
        namedtype.NamedType('version', rfc2315.Version()),
        namedtype.NamedType('value', univ.OctetString())
    )


class AppReceipt(univ.SetOf):
    """Apple App Receipt"""

    componentType = AppReceiptField()


class IAPReceiptFieldType(univ.Integer):
    """Apple In-App Purchase Receipt named field type"""

    namedValues = namedval.NamedValues(
        ('quantity', TYPE_IN_APP_QUANTITY),
        ('product_id', TYPE_IN_APP_PRODUCT_ID),
        ('transaction_id', TYPE_IN_APP_TRANSACTION_ID),
        ('purchase_date', TYPE_IN_APP_PURCHASE_DATE),
        ('original_transaction_id', TYPE_IN_APP_ORIGINAL_TRANSACTION_ID),
        ('original_purchase_date', TYPE_IN_APP_ORIGINAL_PURCHASE_DATE),
        ('expires_date', TYPE_IN_APP_EXPIRES_DATE),
        ('web_order_line_item_id', TYPE_IN_APP_WEB_ORDER_LINE_ITEM_ID),
        ('cancellation_date', TYPE_IN_APP_CANCELLATION_DATE),
    )


class IAPReceiptField(AppReceiptField):
    """Apple In-App Purchase Receipt field"""

    pass


class IAPReceiptFields(univ.SetOf):
    """Apple In-App Purchase Receipt fields"""

    componentType = IAPReceiptField()


def _decode_iap(iap_data):
    in_app_map = FieldMap(IN_APP_FIELD_MAP)
    in_app, _ = decoder.decode(iap_data, asn1Spec=IAPReceiptFields())

    result = {}
    for index in range(len(in_app)):
        field = in_app[index]
        field_type = field['type']
        field_name = IAPReceiptFieldType.namedValues.getName(field_type)

        if not field_name:
            # We don't know what this field is
            continue

        value = field['value']
        result[field_name] = in_app_map.convert(field_type, value)

    return result


def decode_receipt(data):
    receipt_map = FieldMap(RECEIPT_FIELD_MAP)

    receipt, _ = decoder.decode(data, asn1Spec=AppReceipt())

    # Which fields are lists
    list_fields = [TYPE_IN_APP]

    result = {}
    for index in range(len(receipt)):
        field = receipt[index]
        field_type = field['type']
        field_name = AppReceiptFieldType.namedValues.getName(field_type)

        if not field_name:
            # We don't know what this field is
            continue

        value = field['value']
        if field_type in list_fields:
            result.setdefault(field_name, []).append(_decode_iap(value))
        else:
            result[field_name] = receipt_map.convert(field_type, value)

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
        elif status >= 21100 and status <= 12299:
            # There was an internal data access error
            raise RetryReceiptValidation(
                content, 'Internal data access error %s. Retry' % status)
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


def validate_receipt_is_active(data, timedelta, is_test=False, product_id=None):
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

        # If we were given a product_id, make sure this iap is for that same
        # product_id
        if product_id is not None and iap.get('product_id') != product_id:
            # Ignore this IAP as it is for a different product
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

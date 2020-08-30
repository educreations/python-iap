import base64
import datetime
import logging

from asn1crypto.cms import ContentInfo
from asn1crypto.core import (
    Integer,
    OctetString,
    Sequence,
    SetOf,
    UTF8String,
    IA5String,
)
from OpenSSL import crypto
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

from .settings import (
    DEBUG_BUNDLE_ID,
    DEBUG_PRODUCT_IDS,
    IAP_SHARED_SECRET,
    PRODUCTION_BUNDLE_ID,
    PRODUCTION_PRODUCT_IDS,
    PRODUCTION_VERIFICATION_URL,
    SANDBOX_VERIFICATION_URL,
    TRUSTED_ROOT_FILE,
)


log = logging.getLogger(__name__)


def load_pkcs7_bio_der(p7_der):
    """
    Load a PKCS7 object from a PKCS7 DER blob.
    Return PKCS7 object.
    """
    try:
        return crypto.load_pkcs7_data(crypto.FILETYPE_ASN1, p7_der)
    except crypto.Error:
        raise InvalidReceipt("Unable to load PCKS7 data")


def verify_receipt_sig(raw_data):
    trusted_store = crypto.X509Store()

    with open(TRUSTED_ROOT_FILE, "rb") as ca_cert_file:
        trusted_root_data = ca_cert_file.read()

    trusted_root = crypto.load_certificate(crypto.FILETYPE_ASN1, trusted_root_data)

    trusted_store.add_cert(trusted_root)

    try:
        pkcs_container = ContentInfo.load(raw_data)
    except ValueError as exc:
        log.error("Unable to decode receipt data {}", exc)
        raise InvalidReceipt("Unable to decode receipt data")

    # Extract the certificates, signature, and receipt_data
    certificates = pkcs_container["content"]["certificates"]
    signer_info = pkcs_container["content"]["signer_infos"][0]
    receipt_data = pkcs_container["content"]["encap_content_info"]["content"]

    # Pull out and parse the X.509 certificates included in the receipt
    itunes_cert_data = certificates[0].chosen.dump()
    itunes_cert = crypto.load_certificate(crypto.FILETYPE_ASN1, itunes_cert_data)

    wwdr_cert_data = certificates[1].chosen.dump()
    wwdr_cert = crypto.load_certificate(crypto.FILETYPE_ASN1, wwdr_cert_data)

    try:
        crypto.X509StoreContext(trusted_store, wwdr_cert).verify_certificate()
        trusted_store.add_cert(wwdr_cert)
    except crypto.X509StoreContextError as exc:
        log.error("Unable to decode wwwdr certificate {}", exc)
        raise InvalidReceipt("Invalid WWDR certificate")

    try:
        crypto.X509StoreContext(trusted_store, itunes_cert).verify_certificate()
    except crypto.X509StoreContextError as exc:
        log.error("Unable to decode iTunes certificate {}", exc)
        raise InvalidReceipt("Invalid iTunes certificate")

    try:
        crypto.verify(
            itunes_cert, signer_info["signature"].native, receipt_data.native, "sha1"
        )
        # Valid data
    except Exception as exc:
        log.error("Signature verification failed {}", exc)
        raise InvalidReceipt("Signature verification failed")

    return receipt_data.native


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
TYPE_IN_APP_IS_IN_INTRO_OFFER_PERIOD = 1719


# See https://developer.apple.com/library/ios/releasenotes/General/ValidateAppStoreReceipt/Chapters/ReceiptFields.html  # noqa
RECEIPT_FIELD_MAP = [
    (TYPE_ENVIRONMENT, "_environment", UTF8String),
    (TYPE_BUNDLE_ID, "bundle_id", UTF8String),
    (TYPE_APPLICATION_VERSION, "application_version", UTF8String),
    (TYPE_OPAQUE_VALUE, "_opaque_value", OctetString),
    (TYPE_SHA1_HASH, "_sha1_hash", OctetString),
    (TYPE_RECEIPT_CREATION_DATE, "creation_date", IA5String),
    (TYPE_IN_APP, "in_app", OctetString),
    (TYPE_ORIGINAL_PURCHASE_DATE, "original_purchase_date", IA5String),
    (TYPE_ORIGINAL_APPLICATION_VERSION, "original_application_version", UTF8String),
    (TYPE_EXPIRATION_DATE, "expiration_date", IA5String),
]

IN_APP_FIELD_MAP = {
    (TYPE_IN_APP_QUANTITY, "quantity", Integer),
    (TYPE_IN_APP_PRODUCT_ID, "product_id", UTF8String),
    (TYPE_IN_APP_TRANSACTION_ID, "transaction_id", UTF8String),
    (TYPE_IN_APP_PURCHASE_DATE, "purchase_date", IA5String),
    (TYPE_IN_APP_ORIGINAL_TRANSACTION_ID, "original_transaction_id", UTF8String),
    (TYPE_IN_APP_ORIGINAL_PURCHASE_DATE, "original_purchase_date", IA5String),
    (TYPE_IN_APP_EXPIRES_DATE, "expires_date", IA5String),
    (TYPE_IN_APP_WEB_ORDER_LINE_ITEM_ID, "web_order_line_item_id", Integer),
    (TYPE_IN_APP_CANCELLATION_DATE, "cancellation_date", IA5String),
    (TYPE_IN_APP_IS_IN_INTRO_OFFER_PERIOD, "is_in_intro_offer_period", Integer),
}


class ReceiptAttributeType(Integer):
    """Apple App Receipt named field type"""

    _map = {type_code: name for type_code, name, _ in RECEIPT_FIELD_MAP}


class ReceiptAttribute(Sequence):
    """Apple App Receipt field"""

    _fields = [
        ("type", ReceiptAttributeType),
        ("version", Integer),
        ("value", OctetString),
    ]


class Receipt(SetOf):
    """Apple App Receipt"""

    _child_spec = ReceiptAttribute


class InAppAttributeType(Integer):
    """Apple In-App Purchase Receipt named field type"""

    _map = {type_code: name for (type_code, name, _) in IN_APP_FIELD_MAP}


class InAppAttribute(Sequence):
    """Apple In-App Purchase Receipt field"""

    _fields = [
        ("type", InAppAttributeType),
        ("version", Integer),
        ("value", OctetString),
    ]


class InAppPayload(SetOf):
    """Apple In-App Purchase Receipt fields"""

    _child_spec = InAppAttribute


def _decode_iap(in_apps):
    in_app_attribute_types_to_class = {
        name: type_class for _, name, type_class in IN_APP_FIELD_MAP
    }

    result = []

    for in_app_data in in_apps:
        in_app = {}

        for attr in InAppPayload.load(in_app_data.native):
            attr_type = attr["type"].native

            if attr_type in in_app_attribute_types_to_class:
                in_app[attr_type] = (
                    in_app_attribute_types_to_class[attr_type]
                    .load(attr["value"].native)
                    .native
                )

        result.append(in_app)

    return result


def decode_receipt(receipt_data):
    log.info("Decoding receipt data")

    receipt = Receipt.load(receipt_data)

    result = {}
    attribute_types_to_class = {
        name: type_class for _, name, type_class in RECEIPT_FIELD_MAP
    }

    in_apps = []
    for attr in receipt:
        attr_type = attr["type"].native

        # Just store the in_apps for now
        if attr_type == "in_app":
            in_apps.append(attr["value"])
            continue

        if attr_type in attribute_types_to_class:
            if attribute_types_to_class[attr_type] is not None:
                try:
                    result[attr_type] = (
                        attribute_types_to_class[attr_type]
                        .load(attr["value"].native)
                        .native
                    )
                except Exception:
                    result[attr_type] = attr["value"].native
            else:
                result[attr_type] = attr["value"].native

    decoded_in_apps = _decode_iap(in_apps)
    result["in_app"] = decoded_in_apps

    result["_sandbox"] = (
        result.get("original_application_version") == "1.0"
        and result.get("_environment") != "Production"
    )

    log.info("Decoded receipt data")

    return result


def parse_receipt(raw_data):
    return decode_receipt(verify_receipt_sig(raw_data))


def validate_receipt_with_apple(data_bytes):
    base64_bytes = base64.b64encode(data_bytes)
    base64_string = base64_bytes.decode("utf-8")
    payload = {"receipt-data": base64_string}

    if IAP_SHARED_SECRET:
        payload["password"] = IAP_SHARED_SECRET

    # Docs at https://developer.apple.com/library/archive/releasenotes/General/ValidateAppStoreReceipt/Chapters/ValidateRemotely.html  # noqa
    for url in (PRODUCTION_VERIFICATION_URL, SANDBOX_VERIFICATION_URL):
        is_production_url = url == PRODUCTION_VERIFICATION_URL

        log.info(
            "Validating receipt with Apple at the {} url".format(
                "production" if is_production_url else "sandbox"
            )
        )

        r = requests.post(url, json=payload)
        r.raise_for_status()
        try:
            content = r.json()
        except JSONDecodeError:
            raise ReceiptValidationException({}, "Unable to read response")

        if "status" not in content:
            raise ReceiptValidationException(content, "Unknown response format")
        status = content.get("status", APPSTORE_STATUS_INVALID_JSON)

        log.info("Received status {} from Apple".format(status))

        if status == APPSTORE_STATUS_INVALID_JSON:
            # The App Store could not read the JSON object you provided.
            raise ReceiptValidationException(content, "Unable to read payload")
        elif status == APPSTORE_STATUS_MALFORMED_RECEIPT_DATA:
            # The data in the receipt-data property was malformed or missing.
            raise ReceiptValidationException(content, "Malformed receipt-data")
        elif status == APPSTORE_STATUS_RECEIPT_AUTHENTICATION:
            # The receipt could not be authenticated.
            raise ReceiptValidationException(
                content, "Receipt is from an unknown source"
            )
        elif status == APPSTORE_STATUS_SHARED_SECRET_MISMATCH:
            # Bad shared secret for the app / auth failed
            # NOTE: Only returned for iOS 6 style transaction receipts for
            # auto-renewable subscriptions.
            raise ReceiptValidationException(
                content, "The shared secret does not match"
            )
        elif status == APPSTORE_STATUS_RECEIPT_SERVER_DOWN:
            # The receipt server is not currently available.
            raise RetryReceiptValidation(content, "Server Unavailable")
        elif status == APPSTORE_STATUS_EXPIRED_SUBSCRIPTION:
            # The receipt is inactive
            # NOTE: Only returned for iOS 6 style transaction receipts for
            # auto-renewable subscriptions. For iOS 7 style app receipts, the
            # status code is reflects the status of the app receipt as a whole.
            # For example, if you send a valid app receipt that contains an
            # expired subscription, the response is 0 because the receipt as a
            # whole is valid.
            raise ReceiptValidationException(content, "Inactive subscription")
        elif status == APPSTORE_STATUS_TEST_ENVIRONMENT_RECEIPT:
            if is_production_url:
                # We need to try the other environment
                log.info("Receipt should be in the sandbox environment")
                continue
            raise ReceiptValidationException(content, "Cannot try another url!")
        elif status == APPSTORE_STATUS_PROD_ENVIRONMENT_RECEIPT:
            raise ReceiptValidationException(content, "We already tried prod!")
        elif status == APPSTORE_STATUS_UNAUTHORIZED_RECEIPT:
            # This receipt could not be authorized. Treated as if the purchase
            # was never made.
            raise NoPurchasesException(content, "The receipt could not be authorized")
        elif status == 21009:
            # This seems to be an internal Apple error. In this case,
            # one should retry the request
            raise RetryReceiptValidation(content, "Internal Apple error. Retry")
        elif (
            APPSTORE_STATUS_INTERNAL_DATA_ACCESS_ERROR_MIN
            <= status
            <= APPSTORE_STATUS_INTERNAL_DATA_ACCESS_ERROR_MAX
        ):
            # There was an internal data access error
            raise RetryReceiptValidation(
                content, "Internal data access error %s. Retry" % status
            )
        elif status != 0:
            raise RetryReceiptValidation(
                content, "Unknown status code %s. Retry" % status
            )

        if "receipt" not in content:
            raise ReceiptValidationException(
                content, "Unable to get receipt from Apple"
            )

        receipt = content.get("receipt", [])
        if not receipt:
            raise ReceiptValidationException(content, "Not enough receipt!")

        # Set the sandbox property
        receipt["_sandbox"] = not is_production_url

        in_app_purchases = receipt.get("in_app", [])
        if not in_app_purchases:
            raise NoPurchasesException(content, "No IAPs for receipt!")

        latest_receipt = receipt.get("latest_receipt")
        if latest_receipt:
            try:
                receipt["latest_receipt_encoded"] = latest_receipt
                receipt["latest_receipt"] = base64.b64decode(latest_receipt)
            except TypeError:
                raise ReceiptValidationException(
                    content, "Cannot decode latest_receipt"
                )

        return content


def validate_device(decoded_receipt, bundle_ids):
    if "bundle_id" not in decoded_receipt:
        raise InvalidReceipt(u"Unknown decoded receipt format!")
    if decoded_receipt["bundle_id"] not in bundle_ids:
        raise InvalidReceipt(
            u"Unexpected bundle_id in decoded receipt {}".format(
                decoded_receipt["bundle_id"]
            )
        )
    return True


def validate_product(decoded_receipt, product_ids):
    # If there are no products in the receipt, they are all ok
    for in_app in decoded_receipt.get("in_app", []):
        if "product_id" not in in_app:
            raise InvalidReceipt(u"Unknown decoded receipt format!")
        if in_app["product_id"] not in product_ids:
            raise InvalidReceipt(
                u"Unexpected product_id in decoded receipt {}".format(
                    in_app["product_id"]
                )
            )
    return True


def validate_production_receipt(decoded_receipt):
    validate_device(decoded_receipt, [PRODUCTION_BUNDLE_ID])
    validate_product(decoded_receipt, PRODUCTION_PRODUCT_IDS)


def validate_debug_receipt(decoded_receipt):
    if not decoded_receipt.get("_sandbox", False):
        raise InvalidReceipt("Debug receipts must be in the sandbox!")

    bundle_ids = (
        [DEBUG_BUNDLE_ID, PRODUCTION_BUNDLE_ID]
        if DEBUG_BUNDLE_ID
        else [PRODUCTION_BUNDLE_ID]
    )

    # The sandbox can have both production and debug bundle and product ids.
    # This is because when the app is in review, they test on the sandbox,
    # but are using a production build of the app.
    validate_device(decoded_receipt, bundle_ids)
    validate_product(decoded_receipt, DEBUG_PRODUCT_IDS | PRODUCTION_PRODUCT_IDS)


def validate_receipt_is_active(data, timedelta, is_test=False, product_id=None):
    # Establish grace period
    delta_kwargs = {"minutes": 1} if is_test else {"days": 1}
    grace_period = datetime.timedelta(**delta_kwargs)

    # Check with Apple
    try:
        updated_content = validate_receipt_with_apple(data)
    except RetryReceiptValidation:
        # Try one more time
        log.warn("The first attempt to validate failed, trying one more time")
        updated_content = validate_receipt_with_apple(data)

    # Validate the device and product are ok
    local_validation = (
        validate_debug_receipt if is_test else validate_production_receipt
    )
    local_validation(updated_content["receipt"])

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
        "latest_receipt_info", updated_content["receipt"]["in_app"]
    )

    # Ensure the updated receipt has an active subscription.
    for iap in iaps:
        if iap.get("cancellation_date"):
            # This iap is canceled. Ignore it
            continue

        # If we were given a product_id, make sure this iap is for that same
        # product_id
        if product_id is not None and iap.get("product_id") != product_id:
            # Ignore this IAP as it is for a different product
            continue

        # Look for an expires_date
        expires_date_ms = int(iap.get("expires_date_ms", 0))
        if expires_date_ms:
            # See if this iap is expired
            expires_date_sec = expires_date_ms / 1000.0
            expires_date = datetime.datetime.utcfromtimestamp(expires_date_sec)
            if datetime.datetime.utcnow() < expires_date + grace_period:
                return
        else:
            # Check the subscription period
            purchase_date_sec = int(iap["original_purchase_date_ms"]) / 1000.0
            purchase_date = datetime.datetime.utcfromtimestamp(purchase_date_sec)
            expires_date = purchase_date + timedelta
            if datetime.datetime.utcnow() < expires_date + grace_period:
                return
    raise NoActiveReceiptException(
        updated_content, "No active IAP was found in the receipt"
    )

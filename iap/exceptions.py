APPSTORE_STATUS_INVALID_JSON = 21000
APPSTORE_STATUS_MALFORMED_RECEIPT_DATA = 21002
APPSTORE_STATUS_RECEIPT_AUTHENTICATION = 21003
APPSTORE_STATUS_SHARED_SECRET_MISMATCH = 21004
APPSTORE_STATUS_RECEIPT_SERVER_DOWN = 21005
APPSTORE_STATUS_EXPIRED_SUBSCRIPTION = 21006
APPSTORE_STATUS_TEST_ENVIRONMENT_RECEIPT = 21007
APPSTORE_STATUS_PROD_ENVIRONMENT_RECEIPT = 21008
APPSTORE_STATUS_UNAUTHORIZED_RECEIPT = 21010
APPSTORE_STATUS_INTERNAL_DATA_ACCESS_ERROR_MIN = 21100
APPSTORE_STATUS_INTERNAL_DATA_ACCESS_ERROR_MAX = 21199


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

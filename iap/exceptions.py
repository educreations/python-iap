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

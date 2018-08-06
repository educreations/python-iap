import os

from iap.utils import parse_receipt

RECEIPT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'receipt.bin')


def test_parse_receipt():
    with open(RECEIPT_FILE, 'rb') as r:
        receipt_data = r.read()

    assert r is not None

    receipt_info = parse_receipt(receipt_data)
    assert receipt_info
    for key in (
            'application_version', 'bundle_id', 'creation_date',
            'original_application_version', 'original_purchase_date', 'in_app'):
        assert key in receipt_info

    in_apps = receipt_info['in_app']
    for iap in in_apps:
        for key in (
                'quantity', 'product_id', 'original_transaction_id',
                'transaction_id', 'original_purchase_date'):
            assert key in iap

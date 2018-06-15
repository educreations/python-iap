from django.conf import settings

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

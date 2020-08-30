import os
import urllib

TRUSTED_ROOT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "AppleIncRootCertificate.cer"
)

SECRET_KEY = "notsecr3t"

IAP_SETTINGS = {
    "TRUSTED_ROOT_FILE": TRUSTED_ROOT_FILE,
    "PRODUCTION_BUNDLE_ID": "com.educreations.ios.Educreations",
}

if not os.path.isfile(TRUSTED_ROOT_FILE):
    try:
        trusted_root_data = urllib.urlretrieve(
            "https://www.apple.com/appleca/AppleIncRootCertificate.cer",
            TRUSTED_ROOT_FILE,
        )
    except AttributeError:
        # Python 3
        trusted_root_data = urllib.request.urlretrieve(
            "https://www.apple.com/appleca/AppleIncRootCertificate.cer",
            TRUSTED_ROOT_FILE,
        )

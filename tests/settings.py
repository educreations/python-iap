import os
import urllib

CA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apple_root.pem")

SECRET_KEY = "notsecr3t"

IAP_SETTINGS = {
    "CA_FILE": CA_FILE,
    "PRODUCTION_BUNDLE_ID": "com.educreations.ios.Educreations",
}

if not os.path.isfile(CA_FILE):
    trusted_root_data = urllib.urlretrieve(
        "https://www.apple.com/appleca/AppleIncRootCertificate.cer", CA_FILE
    )

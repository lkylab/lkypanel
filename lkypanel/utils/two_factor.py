import pyotp
import qrcode
import io
import base64

def generate_otp_secret():
    """Generate a random base32 encoded TOTP secret."""
    return pyotp.random_base32()

def get_totp_uri(username, secret, issuer_name="LkyPanel"):
    """Get the provisioning URI for a TOTP secret."""
    return pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer_name)

def generate_qr_code_base64(uri):
    """Generate a base64-encoded PNG QR code image for a URI."""
    img = qrcode.make(uri)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def verify_otp_code(secret, code):
    """Verify a TOTP code against a secret."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code)

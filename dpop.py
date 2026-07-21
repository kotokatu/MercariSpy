import time
import uuid
import jwt
import base64
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization


class DPoPGenerator:
    """
    Generates DPoP proof JWT for Mercari API.
    Keeps the same EC key between launches.
    """

    def __init__(self, key_file="dpop_private_key.pem"):

        self.key_file = Path(key_file)

        if self.key_file.exists():
            self.private_key = self._load_key()
        else:
            self.private_key = self._create_key()
            self._save_key()


        self.public_key = self.private_key.public_key()


    def _create_key(self):
        return ec.generate_private_key(
            ec.SECP256R1()
        )


    def _save_key(self):

        pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        self.key_file.write_bytes(pem)


    def _load_key(self):

        pem = self.key_file.read_bytes()

        return serialization.load_pem_private_key(
            pem,
            password=None
        )


    def _get_jwk(self):

        numbers = self.public_key.public_numbers()

        x = numbers.x.to_bytes(
            32,
            byteorder="big"
        )

        y = numbers.y.to_bytes(
            32,
            byteorder="big"
        )


        return {
            "kty": "EC",
            "crv": "P-256",
            "x": base64.urlsafe_b64encode(x)
                .decode()
                .rstrip("="),

            "y": base64.urlsafe_b64encode(y)
                .decode()
                .rstrip("=")
        }


    def generate(
        self,
        url: str,
        method: str = "POST"
    ):

        now = int(time.time())

        payload = {
            "iat": now,
            "jti": str(uuid.uuid4()),
            "htu": url,
            "htm": method,
            "uuid": str(uuid.uuid4())
        }


        headers = {
            "typ": "dpop+jwt",
            "alg": "ES256",
            "jwk": self._get_jwk()
        }


        return jwt.encode(
            payload,
            self.private_key,
            algorithm="ES256",
            headers=headers
        )
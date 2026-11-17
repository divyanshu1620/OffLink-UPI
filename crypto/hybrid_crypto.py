import os
import json
import base64
import hashlib
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class HybridCryptoService:
    def __init__(self):
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        self.public_key = self.private_key.public_key()

    def get_public_key_b64(self) -> str:
        der = self.public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return base64.b64encode(der).decode('utf-8')

    def hash_ciphertext(self, base64_ciphertext: str) -> str:
        return hashlib.sha256(base64_ciphertext.encode('utf-8')).hexdigest()

    def encrypt(self, payload_dict: dict) -> str:
        plaintext = json.dumps(payload_dict).encode('utf-8')

        aes_key = AESGCM.generate_key(bit_length=256)
        iv = os.urandom(12)
        aesgcm = AESGCM(aes_key)

        aes_ciphertext = aesgcm.encrypt(iv, plaintext, None)

        enc_aes_key = self.public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        combined = enc_aes_key + iv + aes_ciphertext
        return base64.b64encode(combined).decode('utf-8')

    def decrypt(self, base64_ciphertext: str) -> dict:
        combined = base64.b64decode(base64_ciphertext)
        if len(combined) < (256 + 12 + 16):
            raise ValueError("Ciphertext too short")

        enc_aes_key = combined[:256]
        iv = combined[256:268]
        aes_ciphertext = combined[268:]

        aes_key = self.private_key.decrypt(
            enc_aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        aesgcm = AESGCM(aes_key)
        plaintext = aesgcm.decrypt(iv, aes_ciphertext, None)
        return json.loads(plaintext.decode('utf-8'))
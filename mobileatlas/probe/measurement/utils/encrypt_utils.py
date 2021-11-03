import base64
from Crypto.Hash import SHA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA

# RSA/ECB/OAEPWithSHA-1AndMGF1Padding
def encrypt_telekom(key, plain_text):
    pubkey = RSA.importKey(base64.b64decode(key))
    cipher = PKCS1_OAEP.new(pubkey, hashAlgo=SHA)
    encrypted = cipher.encrypt(plain_text.encode('utf-8'))
    return base64.b64encode(encrypted).decode('utf-8')
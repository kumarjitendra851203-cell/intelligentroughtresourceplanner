import hashlib, hmac, os, time
import jwt
from . import config
def _k(p, s): return hashlib.scrypt(p.encode(), salt=s, n=2**14, r=8, p=1).hex()
def hash_pw(p):
    s = os.urandom(16); return s.hex() + "$" + _k(p, s)
def check_pw(p, h):
    try:
        s, k = h.split("$"); return hmac.compare_digest(_k(p, bytes.fromhex(s)), k)
    except Exception:
        return False
def make_token(uid):
    return jwt.encode({"sub": str(uid), "exp": int(time.time()) + 7 * 86400}, config.SECRET_KEY, algorithm="HS256")
def read_token(t):
    try:
        return int(jwt.decode(t, config.SECRET_KEY, algorithms=["HS256"])["sub"])
    except Exception:
        return None

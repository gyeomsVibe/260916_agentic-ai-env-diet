import ctypes, threading, time
from multiprocessing.connection import Listener, Client

addr = r"\\.\pipe\claude_u11_probe"
k = b"secret"
L1 = Listener(addr, "AF_PIPE", authkey=k)
try:
    L2 = Listener(addr, "AF_PIPE", authkey=k)
    print("second_listener_same_name: ALLOWED")
except Exception as e:
    print("second_listener_same_name: denied", type(e).__name__, e.args[:2])

res = []
def srv():
    for label in ("ok", "oversize", "badauth"):
        try:
            c = L1.accept()
            d = c.recv_bytes(maxlength=16)
            c.send_bytes(b"ack:" + d)
            c.close()
        except Exception as e:
            res.append(f"server[{label}] -> {type(e).__name__}")

threading.Thread(target=srv, daemon=True).start()
c = Client(addr, "AF_PIPE", authkey=k); c.send_bytes(b"hi"); print("roundtrip:", c.recv_bytes()); c.close()
c = Client(addr, "AF_PIPE", authkey=k); c.send_bytes(b"x" * 100); time.sleep(0.3)
try:
    Client(addr, "AF_PIPE", authkey=b"wrong")
except Exception as e:
    print("badauth client ->", type(e).__name__)
time.sleep(0.5)
print(res)

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateMutexW.restype = ctypes.c_void_p
h1 = k32.CreateMutexW(None, True, r"Local\claude_u11_probe_mutex"); e1 = ctypes.get_last_error()
h2 = k32.CreateMutexW(None, True, r"Local\claude_u11_probe_mutex"); e2 = ctypes.get_last_error()
print("mutex err first", e1, "second", e2, "(183=ALREADY_EXISTS)")

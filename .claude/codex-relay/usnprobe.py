"""Probe: does NTFS per-file USN / ChangeTime detect same-size content change with restored mtime?"""
import ctypes, os, re, subprocess, time
from ctypes import wintypes

p = os.path.join(os.environ["TEMP"], "usn_probe.txt")


def usn():
    out = subprocess.run(["fsutil", "usn", "readdata", p], capture_output=True)
    m = re.search(rb"USN\s*:\s*(0x[0-9a-fA-F]+)", out.stdout)
    return m.group(1).decode() if m else None


class FILE_BASIC_INFO(ctypes.Structure):
    _fields_ = [("CreationTime", ctypes.c_int64), ("LastAccessTime", ctypes.c_int64),
                ("LastWriteTime", ctypes.c_int64), ("ChangeTime", ctypes.c_int64),
                ("FileAttributes", wintypes.DWORD)]


k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileW.restype = wintypes.HANDLE


def change_time():
    h = k32.CreateFileW(p, 0x80, 7, None, 3, 0x02000000, None)  # FILE_READ_ATTRIBUTES
    info = FILE_BASIC_INFO()
    k32.GetFileInformationByHandleEx(h, 0, ctypes.byref(info), ctypes.sizeof(info))
    k32.CloseHandle(h)
    return info.ChangeTime


with open(p, "w") as f:
    f.write("AAAA")
st = os.stat(p)
u1, c1 = usn(), change_time()
time.sleep(1.1)
with open(p, "w") as f:
    f.write("BBBB")
os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
st2 = os.stat(p)
u2, c2 = usn(), change_time()
print("size same:", st.st_size == st2.st_size, "| mtime restored:", st.st_mtime_ns == st2.st_mtime_ns)
print("USN   before/after:", u1, u2, "-> detects:", u1 is not None and u1 != u2)
print("ChangeTime before/after:", c1, c2, "-> detects:", c1 != c2)

t = time.perf_counter()
for _ in range(200):
    change_time()
print("ChangeTime query x200 secs:", round(time.perf_counter() - t, 3))
os.remove(p)

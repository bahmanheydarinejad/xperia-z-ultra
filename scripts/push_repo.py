import ctypes, subprocess
from ctypes import wintypes

class CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ('Flags', wintypes.DWORD),
        ('Type', wintypes.DWORD),
        ('TargetName', wintypes.LPWSTR),
        ('Comment', wintypes.LPWSTR),
        ('LastWritten', wintypes.FILETIME),
        ('CredentialBlobSize', wintypes.DWORD),
        ('CredentialBlob', ctypes.POINTER(ctypes.c_byte)),
        ('Persist', wintypes.DWORD),
        ('AttributeCount', wintypes.DWORD),
        ('Attributes', ctypes.c_void_p),
        ('TargetAlias', wintypes.LPWSTR),
        ('UserName', wintypes.LPWSTR),
    ]

advapi32 = ctypes.windll.advapi32
CredReadW = advapi32.CredReadW
CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(CREDENTIAL))]
CredReadW.restype = wintypes.BOOL

targets = [
    'GitHub - https://api.github.com/bahmanheydarinejad',
    'GitHub for Visual Studio - https://bahmanheydarinejad@github.com/'
]

tok = None
for t in targets:
    pcred = ctypes.POINTER(CREDENTIAL)()
    if CredReadW(t, 1, 0, ctypes.byref(pcred)):
        blob = bytes(pcred.contents.CredentialBlob[:pcred.contents.CredentialBlobSize])
        for enc in ['utf-8', 'utf-16le']:
            try:
                s = blob.decode(enc)
                if s.startswith('gho_'):
                    tok = s.strip()
                    break
            except:
                pass
    if tok: break

if tok:
    url = f'https://{tok}@github.com/bahmanheydarinejad/xperia-z-ultra.git'
    res = subprocess.run(['git', 'push', url, 'main'], capture_output=True, text=True)
    print('Push return code:', res.returncode)
    print(res.stdout)
    print(res.stderr)
else:
    print('Error: gho token not found in targets.')

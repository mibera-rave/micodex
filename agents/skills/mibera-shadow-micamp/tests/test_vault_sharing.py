"""Windows held-open handles using stdlib ctypes, disposable encrypted state."""
import ctypes,os,sys,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from wallet_bridge import Vault

@unittest.skipUnless(os.name=='nt','Windows sharing semantics')
class Sharing(unittest.TestCase):
    def setUp(self):
        from ctypes import wintypes
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.create=self.kernel.CreateFileW
        self.create.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        self.create.restype=wintypes.HANDLE
        self.close=self.kernel.CloseHandle
        self.close.argtypes=[wintypes.HANDLE];self.close.restype=wintypes.BOOL
        self.t=tempfile.TemporaryDirectory();self.e=patch.dict(os.environ,{'MIBERA_SESSION_PASSWORD':'disposable-sharing-password'});self.e.start()
        self.v=Vault(self.t.name);self.v.put('fixture',{'n':1})
    def tearDown(self):self.e.stop();self.t.cleanup()
    def hold(self,share):
        value=self.create(str(self.v.path/'fixture.enc'),0x80000000,share,None,3,0,None)
        if value in (None,ctypes.c_void_p(-1).value):raise ctypes.WinError(ctypes.get_last_error())
        close=self.close
        class Held:
            def Close(self):
                if not close(value):raise ctypes.WinError(ctypes.get_last_error())
        return Held()
    def test_replace_after_real_reader_releases(self):
        h=self.hold(1);t=threading.Thread(target=lambda:(time.sleep(.20),h.Close()));t.start()
        try:self.v.put('fixture',{'n':2});self.assertEqual(self.v.get('fixture'),{'n':2})
        finally:t.join()
    def test_read_after_exclusive_handle_releases(self):
        h=self.hold(0);t=threading.Thread(target=lambda:(time.sleep(.20),h.Close()));t.start()
        try:self.assertEqual(self.v.get('fixture'),{'n':1})
        finally:t.join()
    def test_bounded_failure_preserves_ciphertext(self):
        before=(self.v.path/'fixture.enc').read_bytes();h=self.hold(1);start=time.monotonic()
        try:self.assertRaises(PermissionError,self.v.put,'fixture',{'n':2});self.assertLess(time.monotonic()-start,2)
        finally:h.Close()
        self.assertEqual((self.v.path/'fixture.enc').read_bytes(),before);self.assertEqual(list(self.v.path.glob('*.tmp')),[])

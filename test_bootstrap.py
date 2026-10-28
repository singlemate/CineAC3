import io
import hashlib
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile
import bootstrap

class Response(io.BytesIO):
    def __init__(self,data):
        super().__init__(data)
        self.headers={'Content-Length':str(len(data))}

class BootstrapTests(unittest.TestCase):
    def archive(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            for name in bootstrap.FILES:
                prefix=f'ffmpeg-{bootstrap.VERSION}-essentials_build/'
                z.writestr(prefix+('bin/' if name.endswith('.exe') else '')+name,name.encode())
        return out.getvalue()

    def test_verified_install(self):
        data=self.archive()
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(bootstrap.urllib.request,'urlopen',return_value=Response(data)), patch.object(bootstrap,'SHA256',hashlib.sha256(data).hexdigest()):
                bootstrap.install(lambda *_:None,threading.Event(),temp)
            for name in bootstrap.FILES:
                self.assertEqual((Path(temp)/name).read_bytes(),name.encode())
            self.assertEqual(len(list(Path(temp).iterdir())),3)

    def test_wrong_hash_preserves_existing(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'ffmpeg.exe';target.write_bytes(b'original')
            with patch.object(bootstrap.urllib.request,'urlopen',return_value=Response(b'bad archive')):
                with self.assertRaises(ValueError):
                    bootstrap.install(lambda *_:None,threading.Event(),temp)
            self.assertEqual(target.read_bytes(),b'original')
            self.assertEqual(len(list(Path(temp).iterdir())),1)

    def test_cancel_leaves_no_installation(self):
        cancelled=threading.Event();cancelled.set()
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(bootstrap.urllib.request,'urlopen',return_value=Response(self.archive())):
                with self.assertRaises(RuntimeError):
                    bootstrap.install(lambda *_:None,cancelled,temp)
            self.assertEqual(list(Path(temp).iterdir()),[])

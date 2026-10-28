"""Fetch an unmodified upstream FFmpeg build; binaries are not redistributed here."""
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

VERSION = '9.0.2'
URL = 'https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip'
SHA256 = '60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba'
FILES = ('ffmpeg.exe', 'ffprobe.exe', 'LICENSE')

def cache_directory():
    return Path(os.environ.get('LOCALAPPDATA', Path.home()/'.cache'))/'CineAC3'/'bin'

def install(progress, cancelled, destination=None):
    destination = Path(destination) if destination else cache_directory()
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.setup-', dir=destination) as temp:
        temp = Path(temp)
        archive = temp/'ffmpeg.zip'
        digest = hashlib.sha256()
        received = 0
        request = urllib.request.Request(URL, headers={'User-Agent':'CineAC3/0.1'})
        with urllib.request.urlopen(request, timeout=30) as response, archive.open('wb') as output:
            total = int(response.headers.get('Content-Length',0))
            while True:
                if cancelled.is_set():
                    raise RuntimeError('Подготовка отменена. Её можно повторить при следующем запуске.')
                data = response.read(256*1024)
                if not data:
                    break
                received += len(data)
                if received > 200*1024*1024:
                    raise ValueError('Неожиданный размер загрузки')
                output.write(data)
                digest.update(data)
                progress(received, total)
        if digest.hexdigest() != SHA256:
            raise ValueError('Контрольная сумма FFmpeg не совпала. Загруженные файлы не установлены.')
        with zipfile.ZipFile(archive) as bundle:
            for name in FILES:
                member = f'ffmpeg-{VERSION}-essentials_build/' + ('bin/' if name.endswith('.exe') else '') + name
                with bundle.open(member) as source, (temp/name).open('wb') as output:
                    shutil.copyfileobj(source,output)
        if cancelled.is_set():
            raise RuntimeError('Подготовка отменена')
        for name in FILES:
            os.replace(temp/name, destination/name)
    return destination

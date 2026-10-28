import os, sys, shutil
from pathlib import Path
BASE = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent

def find_tool(name):
    from bootstrap import cache_directory
    for directory in (BASE / 'bin', BASE, cache_directory()):
        p = directory / (name + ('.exe' if os.name == 'nt' else ''))
        if p.is_file():
            return str(p)
    return shutil.which(name)

def duration(info):
    try:
        return float(info.get('format', {}).get('duration', 0))
    except (ValueError, TypeError):
        return 0.0

def command(source, target, info, selected, bitrate=640, force51=True):
    if bitrate not in (192, 256, 320, 384, 448, 640):
        raise ValueError('Недопустимый битрейт')
    audios = {s['index'] for s in info['streams'] if s.get('codec_type') == 'audio'}
    if not selected or not selected <= audios:
        raise ValueError('Выберите аудиодорожки')
    args = ['-hide_banner', '-nostdin', '-n', '-i', str(source), '-map', '0', '-map_metadata', '0', '-map_chapters', '0', '-c', 'copy', '-copy_unknown']
    for output_index, stream in enumerate(info['streams']):
        index = stream['index']
        args += [f'-map_metadata:s:{output_index}', f'0:s:{index}']
        flags = [k for k, v in stream.get('disposition', {}).items() if v]
        args += [f'-disposition:{output_index}', '+'.join(flags) or '0']
        if index in selected:
            spec = str(output_index)
            args += [f'-c:{spec}', 'ac3', f'-b:{spec}', f'{bitrate}k', f'-ar:{spec}', '48000']
            if force51 or stream.get('channels', 2) > 6:
                args += [f'-ac:{spec}', '6']
            for tag in ('BPS', 'NUMBER_OF_BYTES', 'NUMBER_OF_FRAMES', 'DURATION'):
                for suffix in ('', '-eng'):
                    args += [f'-metadata:s:{spec}', tag + suffix + '=']
    return args + ['-progress', 'pipe:1', '-nostats', '-f', 'matroska', str(target)]

def verify(before, after, selected, force51):
    old, new = (before.get('streams', []), after.get('streams', []))
    if len(old) != len(new):
        raise ValueError('Изменилось количество потоков')
    if len(before.get('chapters', [])) != len(after.get('chapters', [])):
        raise ValueError('Изменилось количество глав')
    for a, b in zip(old, new):
        if a.get('codec_type') != b.get('codec_type'):
            raise ValueError('Изменился тип потока')
        if a['index'] in selected:
            if b.get('codec_name') != 'ac3':
                raise ValueError('Выбранная дорожка не стала AC3')
            if (force51 or a.get('channels', 2) > 6) and b.get('channels') != 6:
                raise ValueError('Не получен шестиканальный звук')
        elif a.get('codec_name') != b.get('codec_name'):
            raise ValueError('Изменился кодек копируемого потока')
    if duration(before) and duration(after) and (abs(duration(before) - duration(after)) > 2):
        raise ValueError('Длительность отличается более чем на 2 секунды')

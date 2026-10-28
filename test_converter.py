"""Run with: python -m unittest -v test_converter (FFmpeg in bin/)."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from engine import command, verify, find_tool

def run(tool, args):
    return subprocess.run([tool]+list(map(str, args)), check=True,
        capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

def probe(p):
    return json.loads(run(find_tool('ffprobe'), ['-v','error','-show_streams',
        '-show_format','-show_chapters','-of','json',p]).stdout)

class ConversionTests(unittest.TestCase):
    def test_rejects_bad_selection(self):
        with self.assertRaises(ValueError):
            command('a', 'b', {'streams':[]}, {3})

    def test_global_stream_indices(self):
        info = {'streams':[{'index':0,'codec_type':'video'},
            {'index':1,'codec_type':'subtitle'},
            {'index':2,'codec_type':'audio','channels':8},
            {'index':3,'codec_type':'attachment'}]}
        args = command('a','b',info,{2})
        self.assertEqual(args[args.index('-c:2')+1], 'ac3')
        self.assertIn('-copy_unknown', args)
        self.assertNotIn('-c:3', args)

    @unittest.skipUnless(find_tool('ffmpeg') and find_tool('ffprobe'), 'FFmpeg required')
    def test_real_dts_and_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p/'font.txt').write_text('attachment payload',encoding='utf-8')
            (p/'sub.srt').write_text('1\n00:00:00,000 --> 00:00:01,500\nHello\n',encoding='utf-8')
            (p/'meta.txt').write_text(';FFMETADATA1\ntitle=Film title\n'
                '[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=2000\ntitle=Chapter one\n',encoding='utf-8')
            source, output = p/'исходник.mkv', p/'результат.mkv'
            ff = find_tool('ffmpeg')
            run(ff, ['-v','error','-f','lavfi','-i','testsrc2=size=64x64:rate=10:duration=2',
                '-f','lavfi','-i','anullsrc=r=48000:cl=5.1',
                '-f','lavfi','-i','sine=frequency=400:duration=2',
                '-i',p/'sub.srt','-f','ffmetadata','-i',p/'meta.txt',
                '-map','0:v','-map','1:a','-map','2:a','-map','3:s',
                '-map_metadata','4','-map_chapters','4',
                '-t','2','-c:v','ffv1','-c:a:0','dca','-strict','-2',
                '-c:a:1','flac','-c:s','srt',
                '-metadata:s:a:0','language=rus','-metadata:s:a:0','title=Main DTS',
                '-metadata:s:a:1','language=eng','-disposition:a:0','default',
                '-disposition:a:1','comment','-attach',p/'font.txt',
                '-metadata:s:t:0','mimetype=text/plain',source])
            original = source.read_bytes()
            before = probe(source)
            run(ff, command(source,output,before,{1}))
            after = probe(output)
            verify(before,after,{1},True)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(after['streams'][1]['channels'],6)
            self.assertEqual(after['streams'][1]['tags']['language'],'rus')
            self.assertEqual(after['streams'][1]['tags']['title'],'Main DTS')
            self.assertEqual(after['streams'][2]['disposition']['comment'],1)
            self.assertEqual(after['format']['tags']['title'],'Film title')
            self.assertEqual(after['chapters'][0]['tags']['title'],'Chapter one')
            for stream in (0,2,3):
                def hashes(file):
                    return run(ff,['-v','error','-i',file,'-map',f'0:{stream}',
                        '-c','copy','-f','streamhash','-hash','sha256','-']).stdout
                self.assertEqual(hashes(source),hashes(output))
            extracted = p/'attachment.txt'
            run(ff,['-v','error','-dump_attachment:t:0',extracted,'-i',output,
                '-map','0:v:0','-t','0.1','-f','null','-'])
            self.assertEqual(extracted.read_bytes(),(p/'font.txt').read_bytes())
            # Existing output must never be overwritten.
            saved = output.read_bytes()
            subprocess.run([ff]+command(source,output,before,{1}),capture_output=True)
            self.assertEqual(output.read_bytes(),saved)

if __name__ == '__main__':
    unittest.main()

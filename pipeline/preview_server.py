"""Loopback-only preview, exposing built reader and just the generated chapter."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote,urlsplit

PROJECT=Path(__file__).resolve().parents[1]
DIST=PROJECT/'reader/dist'
CHAPTER=PROJECT/'library/preview/m0b'


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self,path):
        clean=unquote(urlsplit(path).path)
        root=CHAPTER if clean.startswith('/chapter/') else DIST
        relative=clean[len('/chapter/'):] if root==CHAPTER else clean.lstrip('/')
        resolved=(root/(relative or 'index.html')).resolve()
        if not resolved.is_relative_to(root.resolve()) or any(part.startswith('.') for part in Path(relative).parts):
            return str(DIST/'__denied__')
        return str(resolved)
    def end_headers(self):
        self.send_header('Cache-Control','no-cache')
        super().end_headers()
    def list_directory(self,path):
        self.send_error(404);return None


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=5173);args=parser.parse_args()
    if not (DIST/'index.html').exists(): parser.error('Run npm run build --prefix reader first')
    if not (CHAPTER/'motionscript.json').exists(): parser.error('Build the preview first')
    print(f'MangaMotion preview: http://127.0.0.1:{args.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()

"""Loopback-only review pages; no directory listings, ROMs or raw assets."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ALLOWED = {'.html', '.png', '.json', '.wav', '.svg', '.mp4'}


def permitted(root, url):
    root = Path(root).resolve()
    path = (root / unquote(urlsplit(url).path).lstrip('/')).resolve()
    if path.is_dir():
        path = path / 'index.html'
    return path if path.is_relative_to(root) and path.suffix in ALLOWED and path.is_file() else None


class EvidenceHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        path = permitted(self.directory, self.path)
        if path is None:
            self.send_error(404)
            return None
        self.path = '/' + str(path.relative_to(Path(self.directory).resolve()))
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404)
        return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    ThreadingHTTPServer(('127.0.0.1', args.port),
        partial(EvidenceHandler, directory=str(args.root.resolve()))).serve_forever()

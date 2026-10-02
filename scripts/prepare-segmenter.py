"""Download only the verified SAM 2.1 source/checkpoint into this D: workspace."""
import os
import sys
import urllib.request
import zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from pipeline.cache import page_sha256
from pipeline.adapters.segmenter import SOURCE_REVISION,ARCHIVE_SHA256,WEIGHT_SHA256,verify_source
if root.drive.upper()!='D:' or Path(os.environ.get('TEMP','')).drive.upper()!='D:':raise RuntimeError('Workspace and TEMP must be on D:')
def download(url,path,checksum):
    if not path.resolve().is_relative_to(root):raise ValueError('Download escapes workspace')
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_file() and page_sha256(path)==checksum:return
    temporary=path.with_suffix('.part');urllib.request.urlretrieve(url,temporary)
    if page_sha256(temporary)!=checksum:raise ValueError('Downloaded checksum mismatch; no promotion')
    temporary.replace(path)
archive=root/'.runtime/vendor'/f'sam2-{SOURCE_REVISION}.zip'
download(f'https://codeload.github.com/facebookresearch/sam2/zip/{SOURCE_REVISION}',archive,ARCHIVE_SHA256)
folder=archive.with_suffix('')
if not folder.exists():
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            if not (archive.parent/item.filename).resolve().is_relative_to(archive.parent.resolve()):raise ValueError('Source archive traversal')
        bundle.extractall(archive.parent)
verify_source(root)
download('https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt',root/'models/sam2/sam2.1_hiera_small.pt',WEIGHT_SHA256)
print('Official pinned SAM 2.1 source/checkpoint verified on D:; no Torch upgrade or CUDA extension build.')

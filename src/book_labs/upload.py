"""Validate the exact approved input bundle; never fetch observed data."""
import hashlib
import io
import json
from pathlib import Path
import zipfile
from book_labs.runtime import ROOT

CONTRACT=json.loads(Path(__file__).with_name('input_contract.json').read_text())
DATA=ROOT/'data/raw/capacity-upload'

def verify():
    for name, expected in CONTRACT['files'].items():
        path=DATA/name
        if not path.is_file():
            raise ValueError('Upload the private nb-11-capacity-inputs-v1.zip before running this notebook.')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Uploaded input changed: '+name)

def import_bundle(data):
    if len(data)>10_000_000 or hashlib.sha256(data).hexdigest()!=CONTRACT['archive_sha256']:
        raise ValueError('Wrong or changed private bundle. Expected nb-11-capacity-inputs-v1.zip.')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)) or set(names)!=set(CONTRACT['files'])|{'manifest.json'}:
            raise ValueError('Unexpected archive members')
        if sum(i.file_size for i in archive.infolist())>20_000_000:
            raise ValueError('Archive too large')
        checked={name:archive.read(name) for name in CONTRACT['files']}
        for name,content in checked.items():
            if hashlib.sha256(content).hexdigest()!=CONTRACT['files'][name]:
                raise ValueError('Input checksum mismatch: '+name)
    DATA.mkdir(parents=True,exist_ok=True)
    for name,content in checked.items():
        (DATA/name).write_bytes(content)
    verify()
    print('Verified retained capacity inputs. No live data request was made.')

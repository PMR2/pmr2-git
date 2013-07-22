from cStringIO import StringIO
from os.path import join, dirname
import tarfile
from pmr2.testing.base import TestRequest

ARCHIVE_NAME = 'repodata.tgz'
ARCHIVE_PATH = join(dirname(__file__), ARCHIVE_NAME)
ARCHIVE_REVS = [
    '42a9021e2e4df151c3255b5429899f421b0c3431',
    '67e07ebc8b3a0c646f4a9f898c543ad1a56e1fb8',
    '0a6808653e657eac20d447cf36022010bdbd3253',
    '090ab454beca05a8ab5b5e9bd15c06eaba790a8a',
    '93c2615285898ffaf4ea81611e54a64c99a157cb',
    '0358f183cc3ede11a357a807c80218f74fa4a539',
    'c9de8a045ef5d352441d69b630f924f12d621a77',
    'eab05fccc349fbeb57ade09a197ddc72cd9e4388',
]

def extract_archive(path, archive_path=ARCHIVE_PATH):
    # extraction 
    tf = tarfile.open(archive_path, 'r:gz')
    mem = tf.getmembers()
    for m in mem:
        tf.extract(m, path)
    tf.close()

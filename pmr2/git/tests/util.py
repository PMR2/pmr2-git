from cStringIO import StringIO
from os.path import join, dirname
import tarfile
from pmr2.testing.base import TestRequest

ARCHIVE_NAME = 'repodata.tgz'
ARCHIVE_PATH = join(dirname(__file__), ARCHIVE_NAME)
ARCHIVE_REVS = [
    '42a9021e2e4df151c3255b5429899f421b0c3431',
    'dbe83b457c03f8e5e499b7df245f8ad25ece356d',
    '828a817c0a7a1508e6a605eb5bd0cf827c671af6',
    '44565054bc19b5943184082431bac54312798ffb',
    '4760073867fcd0f174717a011b19f2b7cd04ed13',
    'da9807a87faaebbcdf0f719a3a7835cede4a9c52',
    '5ce98dfd7d9dec8c7b7c6b749dc746336ee57db5',
    'f3e97964e86ac1118dc7509a7f2a85e61feca75c',
]

def extract_archive(path, archive_path=ARCHIVE_PATH):
    # extraction 
    tf = tarfile.open(archive_path, 'r:gz')
    mem = tf.getmembers()
    for m in mem:
        tf.extract(m, path)
    tf.close()

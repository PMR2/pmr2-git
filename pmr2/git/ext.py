from cStringIO import StringIO
from time import gmtime
import tarfile
import zipfile

from dulwich.objects import Tree
from dulwich.objects import Blob

def parse_gitmodules(raw):
    """
    Parse a .gitmodules file.

    raw - the raw string.
    """

    result = {}
    locals_ = {}

    def reset():
        locals_.clear()

    def add_result():
        if locals_.get('added'):
            return

        path = locals_.get('path')
        url = locals_.get('url')

        if (path is None or url is None):
            return
        result[path] = url
        locals_['added'] = True

    for line in raw.splitlines():
        if not line.strip():
            continue 

        if line.startswith('[submodule '):
            reset()
            continue

        try:
            name, value = line.split('=', 1)
        except:
            # too few values?
            continue
        locals_[name.strip()] = value.strip()
        add_result()

    return result

def archive_tgz(repo, commit, rootname='git'):
    """
    Return an archive from a commit.
    """

    prefix = '%s-%s' % (rootname, commit.id[:12])

    def make_tar_info(obj, path):
        """
        node - the tree entry
        obj - object.
        path - the full path to the object.
        """

        tnfo = tarfile.TarInfo('/'.join([prefix, path]))
        tnfo.size = obj.raw_length()
        tnfo.mtime = commit.commit_time
        tnfo.uname = 'root'
        tnfo.gname = 'root'
        return tnfo

    def _files(tf, tree, current_path=None):
        for node in tree.items():
            if current_path:
                name = '/'.join([current_path, node.path])
            else:
                name = node.path
            obj = repo.get_object(node.sha)
            # XXX todo: support symlinks.
            if isinstance(obj, Blob):
                tnfo = make_tar_info(obj, name)
                tf.addfile(tnfo, StringIO(obj.data))
            if isinstance(obj, Tree):
                _files(tf, obj, name)

    stream = StringIO()
    tf = tarfile.TarFile.open(fileobj=stream, mode='w|gz')
    _files(tf, repo.get_object(commit.tree))
    tf.close()

    return stream.getvalue()

def archive_zip(repo, commit, rootname='git'):
    """
    Return an archive from a commit.
    """

    prefix = '%s-%s' % (rootname, commit.id[:12])
    date_time = tuple(gmtime(commit.commit_time))[:6]

    def make_zip_info(obj, path):
        """
        node - the tree entry
        obj - object.
        path - the full path to the object.
        """

        znfo = zipfile.ZipInfo('/'.join([prefix, path]), date_time)
        znfo.file_size = obj.raw_length()
        znfo.compress_type = zipfile.ZIP_DEFLATED
        return znfo

    def _files(zf, tree, current_path=None):
        for node in tree.items():
            if current_path:
                name = '/'.join([current_path, node.path])
            else:
                name = node.path
            obj = repo.get_object(node.sha)
            # Not sure if zip file provide symlinks?
            if isinstance(obj, Blob):
                znfo = make_zip_info(obj, name)
                zf.writestr(znfo, obj.data)
            if isinstance(obj, Tree):
                _files(zf, obj, name)

    stream = StringIO()
    tf = zipfile.ZipFile(stream, mode='w')
    _files(tf, repo.get_object(commit.tree))
    tf.close()

    return stream.getvalue()

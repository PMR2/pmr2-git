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

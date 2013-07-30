def git(request):
    # Git does not provide HTTP_ACCEPT
    # So skip that, check for this
    agent = request.get_header('User-agent')
    if agent:
        return agent.startswith('git/')
    # nothing else to check, assume not Git
    return False


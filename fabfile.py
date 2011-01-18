from fabric.api import local

def test():
    local("nosetests -v --with-gae", capture=False)
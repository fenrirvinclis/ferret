from fabric.api import *

# the user to use for the remote commands
env.user = 'rsinha'
# the servers where the commands are executed
env.hosts = ['yoker']

def pack():
    # create a new source distribution as tarball
    local('python setup.py sdist --formats=gztar', capture=False)

def deploy():
    # figure out the release name and version
    dist = local('python setup.py --fullname', capture=True).strip()
    # upload the source tarball to the temporary folder on the server
    put('dist/%s.tar.gz' % dist, '/tmp/ferretweb.tar.gz')
    # create a place where we can unzip the tarball, then enter
    # that directory and unzip it
    run('mkdir /tmp/ferretweb')
    with cd('/tmp/ferretweb'):
        run('tar xzf /tmp/ferretweb.tar.gz')
        # now setup the package with our virtual environment's
        # python interpreter
        with cd('/tmp/ferretweb/%s' % dist):
            run('/data/www/ferretweb/env/bin/python setup.py install')
    # now that all is set up, delete the folder again
    run('rm -rf /tmp/ferretweb /tmp/ferretweb.tar.gz')
    # and finally touch the .wsgi file so that mod_wsgi triggers
    # a reload of the application
    run('touch /data/www/ferretweb/ferretweb.wsgi')

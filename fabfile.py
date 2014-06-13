#!/usr/bin/env python
"""
Generate the nagios configuration from puppetdb via genreate_poc then
push the configuration to the nagios server.
"""

from fabric.api import env, local, sudo, task, puts, settings, hide
from fabric.api import put
from generate import generate_all

env.host_string = 'yournagiossyserver.fqdn'

TMP_DIR = "/tmp/nagios_tmp"


@task
def deploy(puppetdb_host="puppet", puppetdb_port=8080, puppetdb_apiversion=3):
    " Generate the nagios configuration and push them into production"

    TMP_FILES = "{0}/auto_*.cfg".format(TMP_DIR)

    # Delete the auto_ files from the last run
    local("rm {0}".format(TMP_FILES))

    # Generate the nagios configuration into a temp dir
    puts("Generating files")
    with settings(hide('everything')):
        generate_all(puppetdb_host, puppetdb_port, puppetdb_apiversion)

    # Clean up the current auto_*.cfg on nagios01
    with settings(warn_only=True):
        sudo("rm /etc/nagios3/conf.d/auto_*.cfg")
        sudo("rm {0}".format(TMP_FILES))

    # Copy them to the remote nagios server
    put(TMP_FILES, TMP_DIR)
    sudo("cp {0} /etc/nagios3/conf.d/".format(TMP_FILES))

    # Make sure they are readable by everyone
    sudo("chmod a+r /etc/nagios3/conf.d/auto_*.cfg")

    # Restart nagios on nagios01
    sudo("sudo service nagios3 reload")

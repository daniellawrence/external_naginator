#!/usr/bin/env python
"""
Generate all the nagios configuration files based on puppetdb information.
"""
import sys
import logging
from collections import defaultdict

from pypuppetdb import connect

LOG = logging.getLogger(__file__)

TMP_FILES = "/tmp/nagios_tmp"


def get_nodefacts(db):
    """
    Get all the nodes & facts from puppetdb.

    This can be used to construct hostgroups, etc.

    {
     'hostname': {
            'factname': factvalue,
            'factname': factvalue,
            }
    }
    """
    nodefacts = {}
    for node in db.nodes():
        nodefacts[node.name] = {}
        for f in node.facts():
            nodefacts[node.name][f.name] = f.value
    return nodefacts


def generate_nagios_cfg_type(db, nagios_type, nodefacts):
    """
    Generate a nagios configuration for a single type

    The output of this will be a single file for each type.
    eg.
      auto_hosts.cfg
      auto_checks.cfg
    """

    # This is the namaed used for the configuration files.
    nagios_define_type = nagios_type.replace('Nagios_', '')

    # Write out the generate configuration into files.
    tmp_file = "{0}/auto_{1}.cfg".format(TMP_FILES, nagios_define_type)
    f = open(tmp_file, 'w')

    # Query puppetdb only throwing back the resource that match
    # the Nagios type.
    unique_list = set([])

    # Keep track of sevice to hostname
    servicegroups = defaultdict(list)

    for r in db.resources(query='["=", "type", "%s"]' % nagios_type):

        # Make sure we do not try and make more than one resource for each one.
        if r.name in unique_list:
            LOG.warning("duplicate: %s" % r.name)
            continue
        unique_list.add(r.name)

        # Add servies to service group
        if nagios_define_type == 'service':
            host_name = r.parameters['host_name']
            servicegroups[r.parameters['service_description']].append(host_name)

        # ignore workstatins, laptops and desktops
        if 'workstation' in r.tags and nagios_define_type == 'host':
            hostname = r.name
            if hostname in nodefacts and 'ipaddress_eth0' in nodefacts[hostname]:
                r.parameters['address'] = nodefacts[hostname]['ipaddress_eth0']
            else:
                r.parameters['address'] = "127.0.0.1"

        f.write("define %s {\n" % nagios_define_type)

        # puppet stores the command_name as command, we rewrite this back
        if nagios_define_type == 'command':
            f.write("  %-30s %s\n" % ("command_name", r.name))

        if nagios_define_type == 'host':
            f.write("  %-30s %s\n" % ("host_name", r.name))

        for param_name, param_value in r.parameters.items():

            if not param_value:
                continue
            if param_name in set(['target', 'require', 'tag', 'notify',
                                  'ensure', 'mode']):
                continue

            # Convert all lists into csv values
            if isinstance(param_value, list):
                param_value = ",".join(param_value)

            f.write("  %-30s %s\n" % (param_name, param_value))
        f.write("}\n")
    f.close()

    for servicegroup_name, host_list in servicegroups.items():
        tmp_file = "{0}/auto_servicegroup_{1}.cfg".format(TMP_FILES, servicegroup_name)

        members = []
        for host in host_list:
            members.append("%s,%s" % (host, servicegroup_name))

        f = open(tmp_file, 'w')
        f.write("define servicegroup {\n")
        f.write(" servicegroup_name %s\n" % servicegroup_name)
        f.write(" alias %s\n" % servicegroup_name)
        f.write(" members %s\n" % ",".join(members))
        f.write("}\n")
        f.close()


def generate_all(db):
    # All the facts we know about all the nodes
    nodefacts = get_nodefacts(db)

    # All the resource types know by puppetdb
    TYPES = [
        'Nagios_host',
        'Nagios_hostgroup',
        'Nagios_hostescalation',
        'Nagios_hostdependency',
        'Nagios_hostextinfo',
        'Nagios_service',
        'Nagios_servicegroup',
        'Nagios_serviceescalation',
        'Nagios_servicedependency',
        'Nagios_serviceextinfo',
        'Nagios_contact',
        'Nagios_contactgroup',
        'Nagios_timeperiod',
        'Nagios_command',
    ]

    # Loop over all the nagios types
    for type_ in TYPES:
        generate_nagios_cfg_type(db=db, nagios_type=type_, nodefacts=nodefacts)

    # Generate all the hostgroups based on puppet facts
    generate_hostgroup(nodefacts, "operatingsystem")
    generate_hostgroup(nodefacts, "customfact_pyhsical_location")
    generate_hostgroup(nodefacts, "customfact_network_location")
    generate_hostgroup(nodefacts, "customfact_role")


def generate_hostgroup(nodefacts, fact_name):
    """
    Generate a nagios host group.

    This could use some love for example:
     passing operatingsystem and operatingsystem would work.
    """

    hostgroup = defaultdict(list)
    factvalue = "unknown"

    tmp_file = "{0}/auto_hostgroup_{1}.cfg".format(TMP_FILES, fact_name)
    f = open(tmp_file, 'w')

    for hostname, facts in nodefacts.items():
        factvalue = facts[fact_name]
        hostgroup[factvalue].append(hostname)

    for hostgroup_name, hosts in hostgroup.items():
        f.write("define hostgroup {\n")
        f.write(" hostgroup_name %s_%s\n" % (fact_name, hostgroup_name))
        f.write(" alias %s_%s\n" % (fact_name, hostgroup_name))
        f.write(" members %s\n" % ",".join(hosts))
        f.write("}\n")


def main(hostname, port, api_version):
    # Connect to puppetdb
    db = connect(host=hostname,
                 port=port,
                 api_version=api_version,
                 timeout=20)

    generate_all(db)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--host', action='store', default='localhost',
        help="The hostname of the puppet DB server.")
    parser.add_argument(
        '--port', action='store', default=8080, type=int,
        help="The port of the puppet DB server.")
    parser.add_argument(
        '-V', '--api-version', action='store', default=3, type=int,
        help="The puppet DB version")
    parser.add_argument(
        '-v', '--verbose', action='count', default=0,
        help="Increase verbosity (specify multiple times for more)")

    args = parser.parse_args()

    log_level = logging.WARNING
    if args.verbose == 1:
        log_level = logging.INFO
    elif args.verbose >= 2:
        log_level = logging.DEBUG

    logging.basicConfig(
        level=log_level,
        stream=sys.stderr,
        format='%(asctime)s %(name)s %(levelname)s %(message)s')

    main(args.host, args.port, args.api_version)

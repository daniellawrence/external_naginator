#!/usr/bin/env python
"""
Generate all the nagios configuration files based on puppetdb information.
"""
import sys
import logging
import ConfigParser
from collections import defaultdict

from pypuppetdb import connect

LOG = logging.getLogger(__file__)


class NagiosType(object):
    directives = None

    def __init__(self, db, output_dir,
                 nodefacts=None, query=None, environment=None):
        self.db = db
        self.output_dir = output_dir
        self.environment = environment
        if not nodefacts:
            self.nodefacts = self.get_nodefacts()
        else:
            self.nodefacts = nodefacts
        self.query = query
        self.file = open(self.file_name(), 'w')

    def query_string(self, nagios_type=None):
        if not nagios_type:
            nagios_type = 'Nagios_' + self.nagios_type

        if not self.query:
            return '["=", "type", "%s"]' % (nagios_type)
        query_parts = ['["=", "%s", "%s"]' % q for q in self.query]
        query_parts.append('["=", "type", "%s"]' % (nagios_type))
        return '["and", %s]' % ", ".join(query_parts)

    def file_name(self):
        return "{0}/auto_{1}.cfg".format(self.output_dir, self.nagios_type)

    def generate_name(self, resource):
        self.file.write("  %-30s %s\n" % (self.nagios_type + '_name',
                                          resource.name))

    def generate_parameters(self, resource):
        for param_name, param_value in resource.parameters.items():

            if not param_value:
                continue
            if param_name in set(['target', 'require', 'tag', 'notify',
                                  'ensure', 'mode']):
                continue
            if self.directives and param_name not in self.directives:
                continue

            # Convert all lists into csv values
            if isinstance(param_value, list):
                param_value = ",".join(param_value)

            self.file.write("  %-30s %s\n" % (param_name, param_value))

    def generate(self):
        """
        Generate a nagios configuration for a single type

        The output of this will be a single file for each type.
        eg.
          auto_hosts.cfg
          auto_checks.cfg
        """

        # Query puppetdb only throwing back the resource that match
        # the Nagios type.
        unique_list = set([])

        for r in self.db.resources(query=self.query_string(),
                                   environment=self.environment):
            # Make sure we do not try and make more than one resource
            # for each one.
            if r.name in unique_list:
                LOG.info("duplicate: %s" % r.name)
                continue
            unique_list.add(r.name)

            self.file.write("define %s {\n" % self.nagios_type)
            self.generate_name(r)
            self.generate_parameters(r)
            self.file.write("}\n")
        self.file.close()


class NagiosHost(NagiosType):
    nagios_type = 'host'
    directives = set(['host_name', 'alias', 'display_name', 'address',
                      'parents', 'hostgroups', 'check_command',
                      'initial_state', 'max_check_attempts',
                      'check_interval', 'retry_interval',
                      'active_checks_enabled', 'passive_checks_enabled',
                      'check_period', 'obsess_over_host', 'check_freshness',
                      'freshness_threshold', 'event_handler',
                      'event_handler_enabled', 'low_flap_threshold',
                      'high_flap_threshold', 'flap_detection_enabled',
                      'flap_detection_options', 'process_perf_data',
                      'retain_status_information',
                      'retain_nonstatus_information',
                      'contacts', 'contact_groups', 'notification_interval',
                      'first_notification_delay', 'notification_period',
                      'notification_options', 'notifications_enabled',
                      'stalking_options', 'notes', 'notes_url',
                      'action_url', 'icon_image', 'icon_image_alt',
                      'vrml_image', 'statusmap_image', '2d_coords',
                      '3d_coords', 'use'])

    def generate_name(self, resource):
        if resource.name in self.nodefacts or 'use' in resource.parameters:
            self.file.write("  %-30s %s\n" % ("host_name", resource.name))
        else:
            self.file.write("  %-30s %s\n" % ("name", resource.name))


class NagiosServiceGroup(NagiosType):
    nagios_type = 'servicegroup'
    directives = set(['servicegroup_name', 'alias', 'members',
                      'servicegroup_members', 'notes', 'notes_url',
                      'action_url'])

    def generate(self):
        super(NagiosServiceGroup, self).generate()
        self.generate_auto_servicegroups()

    def generate_auto_servicegroups(self):
        # Query puppetdb only throwing back the resource that match
        # the Nagios type.
        unique_list = set([])

        # Keep track of sevice to hostname
        servicegroups = defaultdict(list)
        for r in self.db.resources(query=self.query_string('Nagios_service'),
                                   environment=self.environment):
            # Make sure we do not try and make more than one resource
            # for each one.
            if r.name in unique_list:
                continue
            unique_list.add(r.name)

            # Add servies to service group
            if 'host_name' in r.parameters:
                host_name = r.parameters['host_name']
                servicegroups[r.parameters['service_description']].append(host_name)

        for servicegroup_name, host_list in servicegroups.items():
            tmp_file = "{0}/auto_servicegroup_{1}.cfg".format(self.output_dir,
                                                              servicegroup_name)

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


class NagiosService(NagiosType):
    nagios_type = 'service'
    directives = set(['host_name', 'hostgroup_name',
                      'service_description', 'display_name',
                      'servicegroups', 'is_volatile', 'check_command',
                      'initial_state', 'max_check_attempts',
                      'check_interval', 'retry_interval',
                      'active_checks_enabled', 'passive_checks_enabled',
                      'check_period', 'obsess_over_service',
                      'check_freshness', 'freshness_threshold',
                      'event_handler', 'event_handler_enabled',
                      'low_flap_threshold', 'high_flap_threshold',
                      'flap_detection_enabled', 'flap_detection_options',
                      'process_perf_data', 'retain_status_information',
                      'retain_nonstatus_information',
                      'notification_interval',
                      'first_notification_delay',
                      'notification_period', 'notification_options',
                      'notifications_enabled', 'contacts',
                      'contact_groups', 'stalking_options', 'notes',
                      'notes_url', 'action_url', 'icon_image',
                      'icon_image_alt', 'use'])

    def generate_name(self, resource):
        if 'host_name' not in resource.parameters:
            self.file.write("  %-30s %s\n" % ("name", resource.name))


class NagiosHostGroup(NagiosType):
    nagios_type = 'hostgroup'
    directives = set(['hostgroup_name', 'alias', 'members',
                      'hostgroup_members', 'notes',
                      'notes_url', 'action_url'])


class NagiosHostEscalation(NagiosType):
    nagios_type = 'hostescalation'


class NagiosHostDependency(NagiosType):
    nagios_type = 'hostdependency'


class NagiosHostExtInfo(NagiosType):
    nagios_type = 'hostextinfo'


class NagiosServiceEscalation(NagiosType):
    nagios_type = 'serviceescalation'


class NagiosServiceDependency(NagiosType):
    nagios_type = 'servicedependency'


class NagiosServiceExtInfo(NagiosType):
    nagios_type = 'serviceextinfo'


class NagiosTimePeriod(NagiosType):
    nagios_type = 'timeperiod'


class NagiosCommand(NagiosType):
    nagios_type = 'command'
    directives = set(['command_name', 'command_line'])


class NagiosContact(NagiosType):
    nagios_type = 'contact'
    directives = set(['contact_name', 'alias', 'contactgroups',
                      'host_notifications_enabled',
                      'service_notifications_enabled',
                      'host_notification_period',
                      'service_notification_period',
                      'host_notification_options',
                      'service_notification_options',
                      'host_notification_commands',
                      'service_notification_commands',
                      'email', 'pager', 'addressx',
                      'can_submit_commands',
                      'retain_status_information',
                      'retain_nonstatus_information'])


class NagiosContactGroup(NagiosType):
    nagios_type = 'contactgroup'
    directives = set(['contactgroup_name', 'alias', 'members',
                      'contactgroup_members'])


class CustomNagiosHostGroup(NagiosType):
    def __init__(self, db, output_dir, name,
                 nodefacts=None,
                 nodes=None,
                 query=None,
                 environment=None):
        self.nagios_type = name
        self.nodes = nodes
        super(CustomNagiosHostGroup, self).__init__(db=db,
                                                    output_dir=output_dir,
                                                    nodefacts=nodefacts,
                                                    query=query,
                                                    environment=environment)

    def generate(self, hostgroup_name, traits):
        traits = dict(traits)
        fact_template = traits.pop('fact_template')
        hostgroup_name = hostgroup_name.split('_', 1)[1]
        hostgroup_alias = traits.pop('name')

        # Gather hosts base on some resource traits.
        members = []
        for node in self.nodes:
            for type_, title in traits.items():
                if not len(list(node.resources(type_, title))) > 0:
                    break
            else:
                members.append(node)

        nagios_hosts = set(
            [h.name for h in self.db.resources(
                query=self.query_string('Nagios_host'),
                environment=self.environment)
             if h.name in self.nodefacts])

        hostgroup = defaultdict(list)
        for node in members or self.nodes:
            if node.name not in nagios_hosts:
                LOG.debug("Skipping host with no nagios_host resource %s" %
                          node.name)
                continue
            facts = self.nodefacts[node.name]
            try:
                fact_name = hostgroup_name.format(**facts)
                fact_alias = hostgroup_alias.format(**facts)
            except KeyError:
                LOG.error("Can't find facts for hostgroup %s" % fact_template)
                raise
            print (fact_name, fact_alias), node
            hostgroup[(fact_name, fact_alias)].append(node)

        # if there are no hosts in the group then exit
        if not hostgroup.items():
            return

        for hostgroup_name, hosts in hostgroup.items():
            tmp_file = "{0}/auto_hostgroup_{1}.cfg".format(self.output_dir,
                                                           hostgroup_name[0])
            f = open(tmp_file, 'w')
            f.write("define hostgroup {\n")
            f.write(" hostgroup_name %s\n" % hostgroup_name[0])
            f.write(" alias %s\n" % hostgroup_name[1])
            f.write(" members %s\n" % ",".join([h.name for h in hosts]))
            f.write("}\n")


class NagiosConfig:
    def __init__(self, hostname, port, api_version, output_dir,
                 nodefacts=None, query=None, environment=None):
        self.db = connect(host=hostname,
                          port=port,
                          api_version=api_version,
                          timeout=20)
        self.db.resources = self.db.resources
        self.output_dir = output_dir
        self.environment = environment
        if not nodefacts:
            self.nodefacts = self.get_nodefacts()
        else:
            self.nodefacts = nodefacts
        self.query = query

    def query_string(self):
        if not self.environment:
            return None
        query_parts = []
        query_parts.append('["=", "%s", "%s"]' % ('catalog-environment',
                                                  self.environment))
        query_parts.append('["=", "%s", "%s"]' % ('facts-environment',
                                                  self.environment))
        return '["and", %s]' % ", ".join(query_parts)

    def get_nodefacts(self):
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
        self.nodes = []
        for node in self.db.nodes(query=self.query_string()):
            self.nodes.append(node)
            nodefacts[node.name] = {}
            for f in node.facts():
                nodefacts[node.name][f.name] = f.value
        return nodefacts

    def generate_all(self):
        for cls in NagiosType.__subclasses__():
            if cls.__name__.startswith('Custom'):
                continue
            inst = cls(db=self.db,
                       output_dir=self.output_dir,
                       nodefacts=self.nodefacts,
                       query=self.query,
                       environment=self.environment)
            inst.generate()


if __name__ == '__main__':
    import argparse

    class ArgumentParser(argparse.ArgumentParser):

        def error(self, message):
            self.print_help(sys.stderr)
            self.exit(2, '%s: error: %s\n' % (self.prog, message))

    parser = ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--output-dir', action='store', required=True,
        help="The directory to write the Nagios config into.")
    parser.add_argument(
        '-c', '--config', action='store',
        help="The location of the configuration file..")
    parser.add_argument(
        '--host', action='store', default='localhost',
        help="The hostname of the puppet DB server.")
    parser.add_argument(
        '--port', action='store', default=8080, type=int,
        help="The port of the puppet DB server.")
    parser.add_argument(
        '-V', '--api-version', action='store', default=4, type=int,
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

    config = None
    if args.config:
        config = ConfigParser.ConfigParser()
        config.readfp(open(args.config))

    query = None
    if config:
        if 'query' in config.sections():
            query = config.items('query')

    try:
        environment = config.get('puppet', 'environment')
    except:
        environment = None

    cfg = NagiosConfig(hostname=args.host,
                       port=args.port,
                       api_version=args.api_version,
                       output_dir=args.output_dir,
                       query=query,
                       environment=environment)
    cfg.generate_all()

    if config:
        for section in config.sections():
            if not section.startswith('hostgroup_'):
                continue
            group = CustomNagiosHostGroup(cfg.db, args.output_dir,
                                          section,
                                          nodefacts=cfg.nodefacts,
                                          nodes=cfg.nodes,
                                          query=query,
                                          environment=environment)
            group.generate(section, config.items(section))

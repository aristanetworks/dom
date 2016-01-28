#!/usr/bin/env python

# Copyright (c) 2015, Arista Networks EOS+
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of rbeapi nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

##############################################################################
# Proactive / Predictive DOM monitoring
#
# Version 3.1 2016-01-27 Jere Julian <jere@arista.com>
#   - Fix issue to skip over interfaces without optical data avail.
# Version 3.0 2015-12-04 Jere Julian <jere@arista.com>
#   Based on 'domm' originally by Mark Berly, Sean Flack, & Andrei Dvornic
#

"""
   DESCRIPTION
        The Digital Optical Monitor script will periodically poll the optical
        power levels of each interface on a switch and generate syslog events
        when the transmit (Tx) or Receive (Rx) power levels change beyond the
        threshold.  Optionally, SNMP v2c traps or v3 informs may be generated,
        as well.

   INSTALLATION
        Arista# copy http://<server>/dom.py flash:
        Arista# bash chmod +x /mnt/flash/dom.py

   CONFIGURATION/DEBUGGING
        Enable eAPI on the switch:
        Arista#configure terminal
        Arista(config)#username arista privilege 15 secret arista
        Arista(config)#management api http-commands
        Arista(config-mgmt-api-http-cmds)#no shutdown

        Arista# bash vi /mnt/flash/dom.py
        ... Then edit the eAPI and SNMP configuration sections.

        Start manually with:
        Arista# bash sudo /mnt/flash/dom.py -p 30 -t 2 --snmp

        Start automatically with:
        Arista(config)#daemon dom
        Arista(config-daemon-dom)#command /mnt/flash/dom.py --tolerance 2 --poll-interval 30
        Arista(config)#end

   COMPATABILITY

   LIMITATIONS
       Not all optical interface types provide Tx and Rx measurements.  See the
       output of 'show interfaces transceiver' to verify the available data.
"""

import datetime
import argparse
import time
import syslog
import sys
import os
import traceback
import ssl
from ctypes import cdll, byref, create_string_buffer
from pprint import pprint, pformat
from jsonrpclib import Server
from jsonrpclib import ProtocolError
from subprocess import call

#############################################################################
# BEGIN CONFIGURATION
#
#
# eAPI connection information:
#   This must be configured to match the switch being monitored.
#   See 'show management api http-commands' on your switch.
#
PROTOCOL = 'https'
USERNAME = 'eapiuser'
PASSWORD = 'admin'
HOSTNAME = 'localhost'
PORT = 443

#
# SNMP_SETTINGS:
#   Configure the snmptrap options to match your trap destination.
#
#     version: 2c|3
#     seclevel: noAuthNoPriv|authNoPriv|authPriv
#     authprotocol: MD5|SHA
#     privprotocol: DES|SHA

SNMP_SETTINGS = {'traphost': 'localhost',
                 'version': '3',
                 'secname': 'eosplus',
                 'seclevel': 'authPriv',
                 'authprotocol': 'MD5',
                 'authpassword': 'eosplus123',
                 'privprotocol': 'DES',
                 'privpassword': 'eosplus123'
                }
#SNMP_SETTINGS = {'traphost': 'localhost',
#                 'community': 'eosplus',
#                 'version': '2c',
#                }

#
# END CONFIGURATION
#############################################################################

# System defaults managed by CLI options:
DEBUG = False   #pylint: disable=C0103
SYSLOG = True   #pylint: disable=C0103
SNMP = False   #pylint: disable=C0103
USE_CUMULATIVE_AVERAGE = False
TOLERANCE = 3
REBASE_POLL_LIMIT = 3
STATUS = {}

class EapiException(Exception):
    """ An EapiException can be raised when there is a communication issue with
    Arista eAPI on a switch. This mechanism is used to skip switches that may
    not be accessible or configured properly, then automatically start
    accessing them once they become available instead of failing.
    """

    pass

def _time_string():
    '''Format time string'''

    ts = time.time()
    return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

def set_proc_name(newname):
    '''Set the process name seen by the OS in ps, for example
    '''
    log("Entering {0}.".format(sys._getframe().f_code.co_name), level='DEBUG')

    # This works on EOS but not on OSX.  Wrapped in try for testability.
    try:
        libc = cdll.LoadLibrary('libc.so.6')
        buff = create_string_buffer(len(newname) + 1)
        buff.value = newname
        libc.prctl(15, byref(buff), 0, 0, 0)
    except:
        log("Unable to set process name", level='DEBUG')

    if DEBUG:
        print "proc_name: {0}\n".format(sys.argv[0])

def parse_cmd_line():
    """Parse the command line options and return an args dict.
    Get any CLI options from the user.
    Returns:
        dict: A dictionary of CLI arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            'Monitor interface optics send SNMP trap on changes in'
            ' average Tx/Rx levels.'))

    parser.add_argument('-c', '--cumulative-average',
                        action='store_true',
                        default=False,
                        help='Use cumulative average as base' + \
                        '(Default: False)'
                       )

    parser.add_argument('-r', '--rebase-poll-limit',
                        type=int,
                        default=3,
                        help='limit of consecutive polls generating log' + \
                        'messages, before resetting the base (default=3)'
                       )

    parser.add_argument('-t', '--tolerance',
                        type=float,
                        default=3,
                        help='variation (in dBm) which triggers messages' + \
                        'to be logged (default=3)'
                       )

    parser.add_argument('-p', '--poll-interval',
                        type=int,
                        default=10,
                        help='polling interval(default=10)'
                       )

    parser.add_argument('-d', '--debug',
                        action='store_true',
                        default=False,
                        help='Send debug information to the console')

    parser.add_argument('--no-syslog',
                        action='store_true',
                        default=False,
                        help='Disable loging to syslog')

    parser.add_argument('--snmp',
                        action='store_true',
                        default=False,
                        help='Send SNMP traps/notices')

    # Hidden options used for testing
    # Values:
    #   parse_only   Only parse the command line.
    #   get          Get one set of interface stats and dump to console.
    #   trap         Send a test snmp trap.
    #   snmp         Add random number to counters to rphm snmptraps
    #                  and display args sent to snmptrap command
    parser.add_argument('--test',
                        type=str,
                        choices=['parse_only', 'get', 'trap', 'snmp'],
                        default='',
                        help=argparse.SUPPRESS)

    my_args = parser.parse_args()

    global DEBUG
    DEBUG = my_args.debug

    if DEBUG:
        print "CLI Args: {0}\n".format(pformat(my_args))

    global SYSLOG
    if my_args.no_syslog:
        SYSLOG = False

    global SNMP
    SNMP = my_args.snmp

    if my_args.rebase_poll_limit < 1:
        parser.error('poll-interval must be greater than one.')
    if my_args.poll_interval < 0:
        parser.error('poll-interval must be greater than zero.')

    global USE_CUMULATIVE_AVERAGE
    USE_CUMULATIVE_AVERAGE = my_args.cumulative_average
    global TOLERANCE
    TOLERANCE = my_args.tolerance
    global REBASE_POLL_LIMIT
    REBASE_POLL_LIMIT = my_args.rebase_poll_limit

    return my_args

def log(msg, level='INFO', error=False):
    """Logging facility setup.
    args:
        msg (str): The message to log.
        level (str): The priority level for the message. (Default: INFO)
                    See :mod:`syslog` for more options.
        error (bool): Flag if this is an error condition.
    """

    if error:
        level = "ERR"
        print "ERROR: {0} ({1}) {2}".format(os.path.basename(sys.argv[0]),
                                            level, msg)

    if DEBUG:
        # Print to console
        print "{0} ({1}) {2}".format(os.path.basename(sys.argv[0]), level, msg)
    else:
        if level == 'DEBUG':
            # Don't send DEBUG messages unless --debug was also set.
            return

    priority = ''.join(["syslog.LOG_", level])
    syslog.syslog(eval(priority), msg)

def notify(msg, level='INFO', error=False, uptime=0, out=sys.stdout):
    """Manage notifications
    args:
        msg (str): The message to log.
        level (str): The priority level for the message. (Default: INFO)
                    See :mod:`syslog` for more options.
        error (bool): Flag if this is an error condition.
    """
    if SYSLOG:
        log(msg, level, error)

    if SNMP:
        send_trap(SNMP_SETTINGS, msg, uptime=uptime, test=False)

    if out != sys.stdout:
        out.write(msg)

def send_trap(snmp_settings, message, uptime=0, test=False):
    """Send an Arista enterprise-specific SNMP trap containing message.

    Args:
        snmp_settings (dict): SNMP v2c or v3 settings.
        message (string): The message to include in the trap
        uptime (string): The device's uptime for the SNMP trap.
        test (bool): Sent a sample trap message? (Default: False)

    Example:

        trap_content = "Device {0} {1}, interface {2}: {3}"\
            " increasing at > {4} per {5} seconds. Found {6}/{7} packets {8}".\
        format(hostname,
               device['modelName'],
               interface,
               counter,
               changes[interface][counter]['threshold'],
               interval,
               changes[interface][counter]['found'],
               changes[interface][counter]['total'],
               changes[interface][counter]['direction'])

        # system uptime
        send_trap(SETTINGS, trap_content, uptime=device['bootupTimestamp'])
    """
    log("Entering {0}.".format(sys._getframe().f_code.co_name), level='DEBUG')

    log("Sending SNMPTRAP to {0}: {1}".format(snmp_settings['traphost'],
                                              message))

    # NOTE: snmptrap caveat: Generates an error when run as unprivileged user.
    #    Failed to create the persistent directory for
    #    /var/net-snmp/snmpapp.conf
    #    http://sourceforge.net/p/net-snmp/bugs/1706/
    #

    # Build the arguments to snmptrap
    trap_args = ['snmptrap']
    trap_args.append('-v')
    trap_args.append(snmp_settings['version'])

    if snmp_settings['version'] == '2c':
        trap_args.append('-c')
        trap_args.append(snmp_settings['community'])

    elif snmp_settings['version'] == '3':
        # Send v3 snmp-inform rathern than a trap
        trap_args.append('-Ci')

        trap_args.append('-l')
        trap_args.append(snmp_settings['seclevel'])
        trap_args.append('-u')
        trap_args.append(snmp_settings['secname'])

        if snmp_settings['seclevel'] in ['authNoPriv', 'authPriv']:
            trap_args.append('-a')
            trap_args.append(snmp_settings['authprotocol'])
            trap_args.append('-A')
            trap_args.append(snmp_settings['authpassword'])

        if snmp_settings['seclevel'] == 'authPriv':
            trap_args.append('-x')
            trap_args.append(snmp_settings['privprotocol'])
            trap_args.append('-X')
            trap_args.append(snmp_settings['privpassword'])
    else:
        log("Unknown snmp version '{0}' specified in the config file.".
            format(snmp_settings['version']))
    trap_args.append(snmp_settings['traphost'])

    #.iso.org.dod.internet.private. .arista
    # enterprises.30065
    enterprise_oid = '.1.3.6.1.4.1.30065'
    # enterpriseSpecific = 6
    generic_trapnum = '6'
    trap_oid = '.'.join([enterprise_oid, generic_trapnum])

    trap_args.append(str(uptime))
    trap_args.append(enterprise_oid)
    trap_args.append(trap_oid)
    trap_args.append('s')

    if test == "trap":
        message = "TRANSCEIVER_RX_POWER_CHANGE, Ethernet2 (XKE000000000) RX "\
                  "power level has changed by -2.6348 dBm from baseline "\
                  "-5.4035 dBm (2015-12-15 11:33:11)  to -8.0382 dBm "\
                  "(2015-12-15 11:33:33)"
        log("Sending SNMPTRAP to {0} with arguments: {1}".
            format(snmp_settings['traphost'], trap_args), level='DEBUG')

    trap_args.append(message)

    if test == "trap":
        print "snmptrap_args:"
        pprint(trap_args)

    call(trap_args)

def get_interfaces(switch):
    """Get all of the interfaces on a switch.
    Get summary info on all of the interfaces in a switch and return a
        dictionary keyed on interface name.  NOTE: the interfaceIDs are
        missing the space between the interface type and the number.
    args:
        switch (object): A :class:`jsonrpclib` Server object
    returns:
        dict: Dictionary, keyed on interface name (without space), of interface
            summary information."
    Example:
        {u'Ethernet1': {u'autoNegotigateActive': False,
                        u'bandwidth': 10000000000,
                        u'description': u'',
                        u'duplex': u'duplexFull',
                        u'interfaceType': u'EbraTestPhyPort',
                        u'linkStatus': u'connected',
                        u'vlanInformation': {u'interfaceForwardingModel': u'bridged',
                                             u'interfaceMode': u'bridged',
                                             u'vlanId': 1}},
        u'Ethernet2': {u'autoNegotigateActive': False,
                       u'bandwidth': 10000000000,
                       u'description': u'',
                       u'duplex': u'duplexFull',
                       u'interfaceType': u'EbraTestPhyPort',
                       u'linkStatus': u'connected',
                       u'vlanInformation': {u'interfaceForwardingModel': u'bridged',
                                            u'interfaceMode': u'bridged',
                                            u'vlanId': 1}}
    """

    log("Entering {0}.".format(sys._getframe().f_code.co_name), level='DEBUG')
    conn_error = False
    commands = ["show interfaces status"]

    try:
        response = switch.runCmds(1, commands)
    except ProtocolError, err:
        (errno, msg) = err[0]
        # 1002: invalid command
        if errno == 1002:
            log("Invalid EOS interface name ({0})".format(commands), error=True)
        else:
            conn_error = True
            log("ProtocolError while retrieving {0} ([{1}] {2})".
                format(commands, errno, msg),
                error=True)
    except Exception, err:
        conn_error = True
        #   60: Operation timed out
        #   61: Connection refused (http vs https?)
        #  401: Unauthorized
        #  405: Method Not Allowed (bad URL)
        if hasattr(err, 'errno'):
            if err.errno == 60:
                log("Connection timed out: Incorrect hostname/IP or eAPI"
                    " not configured on the switch.", error=True)
            elif err.errno == 61:
                log("Connection refused: http instead of https selected or"
                    " eAPI not configured on the switch.", error=True)
            else:
                log("General Error retrieving {0} ({1})".format(commands,
                                                                err),
                    error=True)
        else:
            # Parse the string manually
            msg = str(err)
            msg = msg.strip('<>')
            err = msg.split(': ')[-1]

            if "401 Unauthorized" in err:
                log("ERROR: Bad username or password")
            elif "405 Method" in err:
                log("ERROR: Incorrect URL")
            else:
                log("HTTP Error retrieving {0} ({1})".format(commands,
                                                             err),
                    error=True)

    if conn_error:
        raise EapiException("Connection error with eAPI")

    # Filter out non-Ethernet interfaces
    for interface in response[0][u'interfaceStatuses'].keys():
        if str(interface)[:8] != 'Ethernet':
            response[0][u'interfaceStatuses'].pop(interface, None)

    return response[0][u'interfaceStatuses']

def check_interfaces(uptime, interface, interfaceinfo, dominfo):
    '''Check the DOM info for each interface on a given switch.
    '''

    log("\nEntering {0} for {1}.".format(sys._getframe().f_code.co_name,
                                         interface), level='DEBUG')

    global STATUS

    try:
        STATUS[interface]
    except (KeyError, NameError):
        STATUS[interface] = XcvrStatusReactor(interface)

    STATUS[interface].uptime = uptime
    STATUS[interface].link_up_now = link_up(interfaceinfo)
    STATUS[interface].check_dom_info(dominfo)

    if DEBUG and STATUS[interface].response:
        pprint(vars(STATUS[interface]))

class XcvrStatusReactor(object):
    '''Interface transceiver status class
    '''

    def __init__(self, interface_string):
        '''Initialize interface transceiver objects
        '''

        log("Entering {0}.".format(sys._getframe().f_code.co_name),
            level='DEBUG')

        self.interface = interface_string
        self.response = {}

        # { 'rx'|'tx' : { <laneId> : power } }
        self.base_power_ = {}
        self.base_power_['rx'] = {}
        self.base_power_['tx'] = {}
        self.base_timestamp_ = None
        self.uptime = 0

        self.link_up_now = False
        self.link_up_on_prev_poll_ = False
        self.poll_iterations_ = 0

        # On consecutive logged messages, we reset the base
        self.logging_polls_ = 0

    def reset_log(self):
        '''On link-transition, reset the historic data.
        '''

        log("Entering {0}.".format(sys._getframe().f_code.co_name),
            level='DEBUG')
        self.base_power_['rx'] = 0
        self.base_power_['tx'] = 0
        self.poll_iterations_ = 0
        self.logging_polls_ = 0
        self.base_timestamp_ = None

    def check_dom_info(self, response, out=sys.stdout):
        '''Analyze the transceiver optical status of the given interface
        response (dict): The interface-specific response from eAPI
                         'show interfaces <ID> transceiver':

                         {u'mediaType': u'100GBASE-SR10',
                          u'rxPower': -30.0,
                          u'temperature': 37.4609375,
                          u'txBias': 0.0,
                          u'txPower': -30.0,
                          u'updateTime': 1449247873.35,
                          u'vendorSn': u'JAS00000006',
                          u'voltage': 3.27}
        '''

        log("Entering {0}.".format(sys._getframe().f_code.co_name),
            level='DEBUG')

        self.response = response

        if not self.link_up_on_prev_poll_:
            if self.link_up_now:
                # Recompute base every time the link comes back up
                log("...came up", level='DEBUG')
                self.compute_base()
        elif self.link_up_now:
            log("...still up", level='DEBUG')
            self.check_power(out=out)
        else:
            # Reset everything if the link goes down
            log("...went down", level='DEBUG')
            self.reset_log()

        self.link_up_on_prev_poll_ = self.link_up_now

    def compute_base(self):
        '''Compute the base DOM info against which we compare on subsequent
        runs
        '''

        log("Entering {0}.".format(sys._getframe().f_code.co_name),
            level='DEBUG')
        self.reset_log()
        self.base_timestamp_ = _time_string()

        if not self.response:
            # No data for this interface
            return

        tx_power = self.response.get(u'txPower', None)
        rx_power = self.response.get(u'rxPower', None)

        if tx_power is None and rx_power is None:
            # No optical data for this interface
            return

        # If an interface is shut then it will report a DOM value of
        # '-inf'. In this case, do not record DOM info.
        # with that DOM info

        if tx_power is "N/A":
            tx_power = None
        if rx_power is "N/A":
            rx_power = None

        if tx_power is not None:
            log('%s: new TX base: %.4f' % (self.interface,
                                           tx_power), level='INFO')
            self.base_power_['tx'] = tx_power

        if rx_power is not None:
            log('%s: new RX base: %.4f' % (self.interface,
                                           rx_power), level='INFO')
            self.base_power_['rx'] = rx_power

    def check_power(self, out=sys.stdout):
        '''Check the status of the optics power levels
        '''

        log("Entering {0}.".format(sys._getframe().f_code.co_name),
            level='DEBUG')

        self.poll_iterations_ += 1
        message_logged = False

        if USE_CUMULATIVE_AVERAGE:
            if self.base_power_['rx']:
                rx_base_power = self.base_power_['rx']
                rx_power = self.response.get(u'rxPower', None)
                self.base_power_['rx'] = \
                    rx_base_power + (rx_power - rx_base_power) / self.poll_iterations_

            if self.base_power_['tx']:
                tx_base_power = self.base_power_['tx']
                tx_power = self.response[u'txPower']
                self.base_power_['tx'] = \
                    tx_base_power + (tx_power - tx_base_power) / self.poll_iterations_

        if self.base_power_['rx']:
            max_rx_power = self.base_power_['rx'] + TOLERANCE
            min_rx_power = self.base_power_['rx'] - TOLERANCE
            rx_power = self.response.get[u'rxPower']
            log('rxBase: {0}: rxPower: {1}'.format(self.base_power_['rx'],
                                                   rx_power), level='DEBUG')
            if not min_rx_power < rx_power < max_rx_power:
                db_change = round(rx_power - self.base_power_['rx'], 4)
                vendor_sn = self.response[u'vendorSn'].rstrip()
                notify('TRANSCEIVER_RX_POWER_CHANGE, {0} ({1}) RX power level '
                       'has changed by {2} dBm from baseline {3} dBm ({4}) '
                       ' to {5} dBm ({6})'
                       .format(self.interface,
                               vendor_sn,
                               db_change,
                               round(self.base_power_['rx'], 4),
                               self.base_timestamp_,
                               round(rx_power, 4),
                               _time_string()),
                       level='WARNING',
                       uptime=self.uptime,
                       out=out)
                #if DEBUG:
                #if out != sys.stdout:
                #    out.write("Rx change")
            message_logged = True

        if self.base_power_['tx']:
            max_tx_power = self.base_power_['tx'] + TOLERANCE
            min_tx_power = self.base_power_['tx'] - TOLERANCE
            tx_power = self.response[u'txPower']
            log('txBase: {0}: txPower: {1}'.format(self.base_power_['tx'],
                                                   tx_power), level='DEBUG')
            if not min_tx_power < tx_power < max_tx_power:
                db_change = round(tx_power - self.base_power_['tx'], 4)
                vendor_sn = self.response[u'vendorSn'].rstrip()
                notify('TRANSCEIVER_TX_POWER_CHANGE, {0} ({1}) TX power level '
                       'has changed by {2} dBm from baseline {3} dBm ({4}) '
                       ' to {5} dBm ({6})'
                       .format(self.interface,
                               vendor_sn,
                               db_change,
                               round(self.base_power_['tx'], 4),
                               self.base_timestamp_,
                               round(tx_power, 4),
                               _time_string()),
                       level='WARNING',
                       uptime=self.uptime,
                       out=out)
                #if DEBUG:
                #out.write("Tx change")
            message_logged = True

        if not message_logged:
            self.logging_polls_ = 0
        else:
            self.logging_polls_ += 1

        if REBASE_POLL_LIMIT and self.logging_polls_ >= REBASE_POLL_LIMIT:
            log('%s: recomputing base' % self.interface, level='INFO')
            self.compute_base()

def link_up(interface):
    '''Determine link status
    '''
    log("Entering {0}.".format(sys._getframe().f_code.co_name), level='DEBUG')
    is_link_up = False
    if interface[u'linkStatus'] == u'connected':
        is_link_up = True

    return is_link_up

def main(args):
    '''Do Stuff.
    '''

    log("Entering {0}.".format(sys._getframe().f_code.co_name), level='DEBUG')

    log("Started up successfully. Entering main loop...")

    switch = Server("{0}://{1}:{2}@{3}:{4}/command-api"\
        .format(PROTOCOL, USERNAME, PASSWORD, HOSTNAME, PORT))
    interfaces = {}
    while True:
        interfaces = get_interfaces(switch)
        response = switch.runCmds(1, ["show interfaces {0} transceiver"
                                      .format(', '.join(interfaces.keys())),
                                      "show version"])
        dominfo = response[0][u'interfaces']
        uptime = int(response[1][u'bootupTimestamp'])

        for interface in interfaces.keys():
            check_interfaces(uptime, str(interface), interfaces[interface],
                             dominfo[interface])

        log("---sleeping for {0} seconds.".format(args.poll_interval),
            level='DEBUG')
        time.sleep(args.poll_interval)

if __name__ == '__main__':
    #TODO: This code is for use on systems which fail when self-signed certs
    #      are used.
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        # Legacy Python that doesn't verify HTTPS certificates by default
        pass
    else:
        # Handle target environment that doesn't support HTTPS verification
        ssl._create_default_https_context = _create_unverified_https_context

    ARGS = parse_cmd_line()
    set_proc_name('dom')

    if ARGS.test == 'parse_only':
        print "\nargs:"
        pprint(ARGS)
        sys.exit(0)

    elif ARGS.test == 'trap':
        send_trap(SNMP_SETTINGS, '', uptime='1449684931', test='trap')
        sys.exit(0)

    try:
        main(ARGS)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception, exception:
        print "{0} FAILURE: {1}".format(sys.argv[0], exception)
        print sys.exc_info()[0]
        print traceback.format_exc()
        sys.exit(1)

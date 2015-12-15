"""Test snmp traps
"""

import sys
import os
import unittest
#import json
import mock

sys.path.append(os.path.join(os.path.dirname(__file__), '../lib'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

#from testlib import get_fixture, function
from dom import send_trap

#from testlib import get_fixture, function

#class TestDomResult(unittest.TestResult:
#    def __init__(self, *args, **kwargs):
#        super(TestDomResult, self).__init__(*args, **kwargs)

class TestSnmp(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestSnmp, self).__init__(*args, **kwargs)
        #self.longMessage = True

    @mock.patch('dom.call')
    def test_send_v2_trap(self, mock_call):
        """Verify snmp v2c traps are called with the right settings
        """
        snmp_settings = {'traphost': 'localhost',
                         'community': 'eosplus',
                         'version': '2c',
                        }

        msg = "This is a test message"

        send_trap(snmp_settings, msg, uptime='', test=True)
        mock_call.assert_called_with(['snmptrap',
                                      '-v', snmp_settings['version'],
                                      '-c', snmp_settings['community'],
                                      snmp_settings['traphost'],
                                      "''",
                                      '.1.3.6.1.4.1.30065',
                                      '.1.3.6.1.4.1.30065.6',
                                      's',
                                      msg])

    @mock.patch('dom.call')
    def test_send_v3_trap(self, mock_call):
        """Verify SNMP v3 informs are generated with the correct options
        """
        snmp_settings = {'traphost': 'localhost',
                         'version': '3',
                         'secname': 'eosplus',
                         'seclevel': 'authPriv',
                         'authprotocol': 'MD5',
                         'authpassword': 'eosplus123',
                         'privprotocol': 'DES',
                         'privpassword': 'eosplus123'
                        }

        msg = "This is a test message"

        send_trap(snmp_settings, msg, uptime='', test=True)
        mock_call.assert_called_with(['snmptrap',
                                      '-v', snmp_settings['version'],
                                      '-Ci',
                                      '-l', snmp_settings['seclevel'],
                                      '-u', snmp_settings['secname'],
                                      '-a', snmp_settings['authprotocol'],
                                      '-A', snmp_settings['authpassword'],
                                      '-x', snmp_settings['privprotocol'],
                                      '-X', snmp_settings['privpassword'],
                                      snmp_settings['traphost'],
                                      "''",
                                      '.1.3.6.1.4.1.30065',
                                      '.1.3.6.1.4.1.30065.6',
                                      's',
                                      msg])

if __name__ == '__main__':
    #unittest.main()
    unittest.main(module=__name__, buffer=True, exit=False)

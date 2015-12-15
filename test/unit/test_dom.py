import sys
import os
import unittest
#import json
import mock
from pprint import pprint
from StringIO import StringIO


sys.path.append(os.path.join(os.path.dirname(__file__), '../lib'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

#from testlib import get_fixture, function
from dom import notify, link_up, check_interfaces, XcvrStatusReactor
#from dom import *
#import dom

#from testlib import get_fixture, function

#class TestDomResult(unittest.TestResult:
#    def __init__(self, *args, **kwargs):
#        super(TestDomResult, self).__init__(*args, **kwargs)

class TestDom(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestDom, self).__init__(*args, **kwargs)
        #response = open(get_fixture('interfaces.json'))
        #self.interfaces = json.load(response)
        #response.close()
        self.longMessage = True
        self.interfaces = {u'Ethernet1':
                           {u'autoNegotiateActive': False,
                            u'autoNegotigateActive': False,
                            u'bandwidth': 10000000000,
                            u'description': u'',
                            u'duplex': u'duplexFull',
                            u'interfaceType': u'Not Present',
                            u'linkStatus': u'notconnect',
                            u'vlanInformation': {u'interfaceForwardingModel': u'bridged',
                                                 u'interfaceMode': u'bridged',
                                                 u'vlanId': 1}
                           }
                          }
        self.dominfo = {u'Ethernet1':
                        {u'mediaType': u'10GBASE-SRL',
                         u'rxPower': -1.3471831500438958,
                         u'temperature': 28.59765625,
                         u'txBias': 5.506,
                         u'txPower': -2.5188953250501633,
                         u'updateTime': 1449776317.0992758,
                         u'vendorSn': u'XKE131102026',
                         u'voltage': 3.2868}
                       }

    def test_notify(self):
        """Verify basics of the notify function
        """
        out = StringIO()

        message = "Test message"
        notify(message, out=out)
        #options = {}

        output = out.getvalue().strip()
        #print "DEBUG: {0}".format(output)
        assert output.startswith(message)

    #@mock.patch('dom.call')
    @mock.patch('dom.log')
    @mock.patch('dom.send_trap')
    def test_notify_snmp(self, mock_log, mock_send_trap):
        """Verify notify with SNMP
        """
        out = StringIO()

        snmp_settings = {'traphost': 'localhost',
                         'version': '3',
                         'secname': 'eosplus',
                         'seclevel': 'authPriv',
                         'authprotocol': 'MD5',
                         'authpassword': 'eosplus123',
                         'privprotocol': 'DES',
                         'privpassword': 'eosplus123'
                        }

        message = "Test message"
        notify(message, out=out)
        #options = {}

        output = out.getvalue().strip()
        print "DEBUG: {0}".format(output)
        assert output.startswith(message)
        #mock_send_trap.assert_called_with(message)
        mock_send_trap.assert_called()
        #mock_call.assert_called_with(message)

    def test_link_up_notconnect(self):
        """Verify link_up on a connected interface
        """
        interface = dict(self.interfaces)
        interface[u'linkStatus'] = u'notconnect'
        result = link_up(interface)
        self.assertEqual(result, False)

    def test_link_up_connected(self):
        """Verify link_up on an unconnected interface
        """
        interface = dict(self.interfaces)
        interface[u'linkStatus'] = u'connected'
        result = link_up(interface)
        self.assertEqual(result, True)

    #@unittest.skip("skipping")
    def test_check_interface_first_down(self):
        """
        """
        interface = u'Ethernet1'

        global status
        status = {}
        status[interface] = XcvrStatusReactor(interface)

        interfaces = dict(self.interfaces)
        dominfo = dict(self.dominfo)
        check_interfaces(str(interface),
                         interfaces[interface],
                         dominfo[interface])
        pprint(vars(status[interface]))
        assert status[interface].link_up_on_prev_poll_ == False
        assert status[interface].link_up_now == False

    #@unittest.skip("skipping")
    def test_check_interface_first_up(self):
        """
        """
        interface = u'Ethernet1'

        global status
        status = {}
        status[interface] = XcvrStatusReactor(interface)

        interfaces = dict(self.interfaces)
        interfaces[interface][u'linkStatus'] = u'connected'
        dominfo = dict(self.dominfo)
        check_interfaces(str(interface), interfaces[interface],
                             dominfo[interface])
        from pprint import pprint
        pprint(vars(status[interface]))
        assert status[interface].link_up_on_prev_poll_ == True
        assert status[interface].link_up_now == False

    @unittest.skip("skipping")
    def test_check_dom_info_first_up(self):
        """
        """
        interface = u'Ethernet1'

        global status
        status = {}
        status[interface] = XcvrStatusReactor(interface)

        interfaces = dict(self.interfaces)
        interfaces[interface][u'linkStatus'] = u'connected'
        dominfo = dict(self.dominfo)
        status[interface].check_dom_info(dominfo)
        from pprint import pprint
        pprint(vars(status[interface]))

    @mock.patch('dom.notify')
    def test_check_dom_info_multiple_rx_increase(self, mock_notify):
        """
        """

        interface = u'Ethernet1'

        #global status
        status = {}

        global DEBUG
        DEBUG = True

        interfaces = dict(self.interfaces)
        interfaces[interface][u'linkStatus'] = u'connected'
        dominfo = dict(self.dominfo)

        status[interface] = XcvrStatusReactor(interface)
        status[interface].link_up_now = True
        status[interface].check_dom_info(dominfo[interface])

        dominfo[interface][u'rxPower'] += 3
        #status[interface].response[u'rxPower'] += 3

        status[interface].check_power()

        args, kwargs = mock_notify.call_args
        #pprint(args[0])
        assert args[0].startswith('TRANSCEIVER_RX_POWER_CHANGE')

    @mock.patch('dom.notify')
    def test_check_dom_info_multiple_rx_decrease(self, mock_notify):
        """
        """

        interface = u'Ethernet1'

        #global status
        status = {}

        global DEBUG
        DEBUG = True

        interfaces = dict(self.interfaces)
        interfaces[interface][u'linkStatus'] = u'connected'
        dominfo = dict(self.dominfo)

        status[interface] = XcvrStatusReactor(interface)
        status[interface].link_up_now = True
        status[interface].check_dom_info(dominfo[interface])

        dominfo[interface][u'rxPower'] += 3
        #status[interface].response[u'rxPower'] -= 3

        status[interface].check_power()

        args, kwargs = mock_notify.call_args
        #print "DEBUG: {0}".format(output)
        assert args[0].startswith("TRANSCEIVER_RX_POWER_CHANGE")

    @mock.patch('dom.notify')
    def test_check_dom_info_multiple_tx_increase(self, mock_notify):
        """
        """

        interface = u'Ethernet1'

        #global status
        status = {}

        global DEBUG
        DEBUG = True

        interfaces = dict(self.interfaces)
        interfaces[interface][u'linkStatus'] = u'connected'
        dominfo = dict(self.dominfo)

        status[interface] = XcvrStatusReactor(interface)
        status[interface].link_up_now = True
        status[interface].check_dom_info(dominfo[interface])

        dominfo[interface][u'txPower'] += 3
        #status[interface].response[u'txPower'] += 3

        status[interface].check_power()

        args, kwargs = mock_notify.call_args
        assert args[0].startswith("TRANSCEIVER_TX_POWER_CHANGE")

    @mock.patch('dom.notify')
    def test_check_dom_info_multiple_tx_decrease(self, mock_notify):
        """
        """

        interface = u'Ethernet1'

        #global status
        status = {}

        interfaces = dict(self.interfaces)
        interfaces[interface][u'linkStatus'] = u'connected'
        dominfo = dict(self.dominfo)

        status[interface] = XcvrStatusReactor(interface)
        status[interface].link_up_now = True
        status[interface].check_dom_info(dominfo[interface])

        dominfo[interface][u'txPower'] += 3
        #status[interface].response[u'txPower'] -= 3

        status[interface].check_power()

        args, kwargs = mock_notify.call_args
        assert args[0].startswith("TRANSCEIVER_TX_POWER_CHANGE")

if __name__ == '__main__':
    #unittest.main()
    unittest.main(module=__name__, buffer=True, exit=False)

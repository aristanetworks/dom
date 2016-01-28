
# iSNMP server for testing the Digital Optical Monitor (dom.py)

## Overview

Tto enable testing of SNMP traps from the Digital Optical Monitor script, you
can use the included snmptrapd.conf and script to start an snmp-server to
receive test traps.

## Requirements

- net-snmp: ‘snmptrap’ (RedHat: `sudo yum install net-snmp`)

## Usage / Configuration

Configure dom.py to send traps to the IP address of the device where you will
run the test snmp server.  Ensure credentials in the script for SNMP v2c or v3
match those in snmptrapd.conf.   Use the included `snmptrapd-start.sh` script
to start snmptrapd, then in another terminal, run dom.py.  The snmptrap server
may be stopped with `CTRL+C`.

```
    #
    # eAPI connection information:
    #   This must be configured to match the switch being monitored.
    #   See 'show management api http-commands' on your switch.
    #
    PROTOCOL = 'https'
    USERNAME = 'eapi'
    PASSWORD = 'admin'
    #HOSTNAME = '10.68.49.142'
    #HOSTNAME = '10.68.49.140'
    HOSTNAME = '10.81.108.137'
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
```

The script has several hidden test flags which may be passed on the CLI for
testing. SNMP configuration may be tested by using the hidden --test option
which will send 1 sample trap/inform to the traphost.

```
./dom.py --test trap
```

Example:
```
$ ./snmptrapd-start.sh
NET-SNMP version 5.7.2
2015-12-15 12:40:06 UDP: [127.0.0.1]:52636->[127.0.0.1]:162 [UDP: [127.0.0.1]:52636->[127.0.0.1]:162]:
SNMPv2-MIB::snmpTrapOID.0 = OID: SNMPv2-SMI::enterprises.30065  SNMPv2-SMI::enterprises.30065.6 = STRING: “Test trap from the Digital Optical Monitor.”

2015-12-15 13:06:02 UDP: [127.0.0.1]:49613->[127.0.0.1]:162 [UDP: [127.0.0.1]:49613->[127.0.0.1]:162]:
DISMAN-EVENT-MIB::sysUpTimeInstance = Timeticks: (1449684931) 167 days, 18:54:09.31 SNMPv2-MIB::snmpTrapOID.0 = OID: SNMPv2-SMI::enterprises.30065  SNMPv2-SMI::enterprises.30065.6 = STRING: “TRANSCEIVER_RX_POWER_CHANGE, Ethernet2 (XKE000000000) RX power level has changed by -2.6348 dBm from baseline -5.4035 dBm (2015-12-15 11:33:11)  to -8.0382 dBm (2015-12-15 11:33:33)”

^C2015-12-15 13:09:11 NET-SNMP version 5.7.2 Stopped.
Stopping snmptrapd
```

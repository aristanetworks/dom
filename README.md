# Digital Optical Monitor (dom.py)

## Overview

The Digital Optical Monitor script will periodically poll the optical power
levels of each interface on a switch and generate syslog events when the
transmit (Tx) or Receive (Rx) power levels change beyond the threshold.  
Optionally, SNMP v2c traps or v3 informs may be generated, as well.

## License

 This is licensed under the [BSD3 license](../blob/master/LICENSE).

## Requirements

- net-snmp: ‘snmptrap’ MUST be in the PATH (included in EOS)
- jsonrpclib: for access to Arista  eAPI (included in EOS)

## Installation / Configuration

Copy dom.py to a linux system or a directly to a switch.  Edit the script and
modify the switch eAPI configuration information and, optionally, the SNMP
trap destination and required options.

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

Make the script executable, then, optionally, configure it to start
automatically on-boot.

SNMP configuration may be tested by using the hidden --test option which will
send 1 sample trap/inform to the traphost.

```
./dom.py --test snmp
```

# Usage

```
    ./dom.py --help
    usage: dom.py [-h] [-c] [-r REBASE_POLL_LIMIT] [-t TOLERANCE]
                  [-p POLL_INTERVAL] [-d] [--no-syslog] [--snmp]

    Monitor interface optics send SNMP trap on changes in average Tx/Rx levels.

    optional arguments:
      -h, --help            show this help message and exit
      -c, --cumulative-average
                            Use cumulative average as base(Default: False)
      -r REBASE_POLL_LIMIT, --rebase-poll-limit REBASE_POLL_LIMIT
                            limit of consecutive polls generating logmessages,
                            before resetting the base (default=3)
      -t TOLERANCE, --tolerance TOLERANCE
                            variation (in dBm) which triggers messagesto be logged
                            (default=3)
      -p POLL_INTERVAL, --poll-interval POLL_INTERVAL
                            polling interval(default=10)
      -d, --debug           Send debug information to the console
      --no-syslog           Disable loging to syslog
      --snmp                Send SNMP traps/notices
```

Example:

```
./dom.py -d -t 1 -p 10 -c
```

Starting from within Arista EOS::

EOS eAPI must be configured on each monitored device.  At a minimum, this requires:

```
EOS#configure terminal
EOS(config)#username eapiuser privilege 15 secret somepassword
EOS(config)#management api http-commands
EOS(config-mgmt-api-http-cmds)#no shutdown
```

To automatically start dom the switch on-boot, add the following:

```
EOS(config)#daemon dom
EOS(config-daemon-dom)#command /mnt/flash/dom.py --tolerance 2 --poll-interval 30
EOS(config)#end
```

## Monitoring

### EOS

```
EOS#show processes | include dom
10159  0.1  1.4 ?        S    03:21:23 00:00:00 rphm     -d -i --dlopen -p -f  -l libLoadDynamicLibs.so procmgr libProcMgrSetup.so --daemonize
```

## Uninstall

```
EOS#config termintal
EOS(config)#no daemon dom
EOS(config)#end
EOS#delete flash:dom.py
```

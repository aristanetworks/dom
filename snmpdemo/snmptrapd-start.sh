###########################################
# Start snmptrapd in the foreground using
# the supplied config to enable a quick
# demo of Remote Port Health Manager (rphm)
###########################################
# sudo snmptrapd -f -L o: -n
#     -f      Do not fork
#     -L o:   output to stdout
#     -n      Do not lookup IPs in DNS
#     -c      Read specified config file

sudo snmptrapd -f -L o: -n -c ./snmptrapd.conf

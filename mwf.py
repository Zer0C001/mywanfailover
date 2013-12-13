#!/usr/bin/python
#conf_file="/etc/mywanfailover/mwf.json"
conf_file="./mwf.json"
from subprocess import call
import os,json,shlex,subprocess
if not os.path.isfile(conf_file):
		print("configuration file not found: "+conf_file)
		exit(1)
try:
	conf_file_handle=open(conf_file,'r')
except IOError:
	print("failed to open config file: "+conf_file)
	exit(1)
configuration=json.load(conf_file_handle)
print configuration
#os.call("ip route show via 94.26.80.9 dev eth3|wc -l")
print "\n"
default_gw=False
other_gw=[]
num_gw=0
for gw in configuration['gateways']:
	if gw.has_key('default') and gw['default']:
		default_gw=gw
	else:
		other_gw.append(gw)
	num_gw+=1
if num_gw<2:
	print "you must specify at least 2 gateways in the config file"
	exit(1)
elif not default_gw:
	print "you must specify which gateway should be the default"
	exit(1)

print "default gateway:"
print default_gw
p = subprocess.Popen(shlex.split("ip route show via "+default_gw["ip"]+" dev "+default_gw["dev"]),stdout=subprocess.PIPE)
numlines=0
for line in p.stdout:
		line=line.split()
		print line
		if line ==["default"]:
			print "is the default"
		numlines+=1
print numlines
#print p.stdout.read()
print "other gateways:"
print other_gw
for gw in other_gw:
	print gw
	p = subprocess.Popen(shlex.split("ip route show via "+gw["ip"]+" dev "+gw["dev"]),stdout=subprocess.PIPE)
	numlines=0
	for line in p.stdout:
		line=line.split()
		print line
		if line ==["default"]:
			print "is the default"
		numlines+=1
	print numlines
	
# ip route replace default via 94.73.63.169 dev eth2
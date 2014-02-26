#!/usr/bin/python

import os,sys,signal,json,shlex,subprocess,time,syslog
## simple_daemon from https://pypi.python.org/pypi/simple_daemon
from simple_daemon import Daemon

class mywanfailover(Daemon):
	def __init__(self,conf_file="/etc/mywanfailover/mwf.json",pidfile="/var/run/mywanfailover.pid",*args,**kwargs):
		super(mywanfailover,self).__init__(pidfile=pidfile,*args,**kwargs)
		syslog.openlog(ident="mywanfailover")
		self.conf_file=conf_file
		self.configuration=None
		self.parse_conf(conf_file)
		self.default_gw=None
		self.current_default_gw=None
		self.other_gw=None
		self.process_gws()
	def sighanle(self,signum,frame):
		if signum==signal.SIGHUP:
			syslog.syslog("SIGHUP received, reloading config file")
			self.parse_conf(self.conf_file)
		else:
			syslog.syslog("unhandled signal received, exiting")
			raise NotImplementedError
	def stop(self,*args,**kwargs):
		syslog.syslog("stopping mywanfailover")
		super(mywanfailover,self).stop(*args,**kwargs)
	def restart(self,*args,**kwargs):
		syslog.syslog("restarting mywanfailover:")
		super(mywanfailover,self).restart(*args,**kwargs)
	def parse_conf(self,conf_file):
		if not os.path.isfile(conf_file):
				syslog.syslog("configuration file not found: "+conf_file)
				exit(1)
		try:
			conf_file_handle=open(conf_file,'r')
		except IOError:
			syslog.syslog("failed to open config file: "+conf_file)
			exit(1)
		configuration=json.load(conf_file_handle)
		conf_file_handle.close()
		self.configuration=configuration
		syslog.syslog(str(configuration))

	def process_gw(self,gw):
		p = subprocess.Popen(shlex.split("ip route show via "+gw["ip"]+" dev "+gw["dev"]),stdout=subprocess.PIPE)
		numlines=0
		is_current_default=False
		for line in p.stdout:
			line=line.split()
			if line ==["default"]:
				is_current_default=True
			numlines+=1
		return(is_current_default,numlines)
	
	def process_gws(self):
		default_gw=False
		current_default_gw=False
		interfaces={}
		other_gw=[]
		num_gw=0
		for gw in self.configuration['gateways']:
			if interfaces.has_key(gw["dev"]):
				syslog.syslog("there should be only one gateway per interface in the config file")
				exit(1)
			interfaces.update({gw["dev"]:True})
			if gw.has_key('default') and gw['default'] and not default_gw:
				default_gw=gw
				is_current_default,numlines=self.process_gw(gw)
				if is_current_default:
					current_default_gw=gw
			elif gw.has_key('default') and gw['default'] and default_gw:
				syslog.syslog("There should be only one default gateway")
				exit(1)
			else:
			  
				other_gw.append(gw)
				is_current_default,numlines=self.process_gw(gw)
				if is_current_default:
					current_default_gw=gw
			num_gw+=1
		if num_gw<2:
			syslog.syslog("you must specify at least 2 gateways in the config file")
			exit(1)
		elif not default_gw:
			syslog.syslog("you must specify which gateway should be the default")
			exit(1)
		self.default_gw=default_gw
		self.current_default_gw=current_default_gw
		self.other_gw=other_gw
	def try_gw(self,gw):
		link_ok=True
		dev_null=open(os.devnull,"w")
		targets=[]
		targets_failed=[]
		if self.configuration.has_key("reenter_gw") and self.configuration["reenter_gw"] and gw.has_key("metric"):
			#syslog.syslog("reentering gw")
			subprocess.call(shlex.split("ip route replace default via "+gw["ip"]+" dev "+gw["dev"]+" metric "+gw["metric"]),stdout=dev_null,stderr=dev_null)
			#syslog.syslog("reentered gw")
		if self.configuration["targets"].has_key(gw["dev"]):
			targets=self.configuration["targets"][gw["dev"]]+self.configuration["targets"]["common"]
		else:
			targets=self.configuration["targets"]["common"]
		if len(targets)==0:
			return False
		for target in targets:
			ping=subprocess.call(shlex.split("ping -c 1 -I "+gw["dev"]+" "+target),stdout=dev_null,stderr=dev_null)
			if ping!=0:
				targets_failed.append(target)
			if len(targets_failed)>self.configuration["tolerance"]:
				link_ok=False
				break
		dev_null.close()
		return(link_ok,targets_failed)
	def switch_to(self,gw):
		subprocess.call(shlex.split("ip route replace default via "+gw["ip"]+" dev "+gw["dev"]))
		if self.configuration.has_key("command_after_switch"):
			if self.configuration["command_after_switch"].has_key("any"):
				subprocess.Popen(shlex.split(self.configuration["command_after_switch"]["any"]))
			if self.configuration["command_after_switch"].has_key(gw["dev"]):
				subprocess.Popen(shlex.split(self.configuration["command_after_switch"][gw["dev"]]))
			elif self.configuration["command_after_switch"].has_key("other"):
				subprocess.Popen(shlex.split(self.configuration["command_after_switch"]["other"]))
			
	def run(self):
		syslog.syslog("starting mywanfailover")
		self.parse_conf(self.conf_file)
		signal.signal(signal.SIGHUP,self.sighanle)
		i=0
		while True:
			self.process_gws()
			default_ok=False
			if self.current_default_gw==self.default_gw:
				link_ok,last_target=self.try_gw(self.default_gw)
				if link_ok:
					i+=1
					if i>=self.configuration["log_int"]:
					  i=0
					  syslog.syslog("link ok")
					default_ok=True
				else:
					syslog.syslog("error in: "+str(last_target))
					default_ok=False
							
			else:
				link_ok,last_target=self.try_gw(self.default_gw)
				if link_ok:
						syslog.syslog("default ok")
						self.switch_to(self.default_gw)
						syslog.syslog("swithed to default:"+str(self.default_gw))
						default_ok=True
				else:
					default_ok=False
			if not default_ok:
				for gw in self.other_gw:
					link_ok=False
					link_ok,last_target=self.try_gw(gw)
					if link_ok:
						if gw!=self.current_default_gw:
							self.switch_to(gw)
							syslog.syslog("switched to "+str(gw))
						break
			time.sleep(self.configuration["check_interval"])
	

mwf=mywanfailover()
if len(sys.argv)==1 or sys.argv[1]=="start":
  mwf.start()
elif sys.argv[1]=="run":
  mwf.run()
elif sys.argv[1]=="stop":
  mwf.stop()
elif sys.argv[1]=="restart":
  mwf.restart()
else:
  print "unknown argument :"+sys.argv[1]


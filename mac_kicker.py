#!/usr/bin/env python3
#
# MIT
# ciko@afra-berlin.de
import pydle, threading, subprocess, time, asyncio

def mac_tester():
	global current_users
	while True:
		# Load the macs. in the loop for auto reload
		macs = {}
		with open("registered_macs", "r") as f:
			for line in f.readlines():
				if len(line.strip()) > 0:
					macs[line.split()[0].upper()] = line.split()[1]

		# Scan for all macs in the current network
		scan_result = subprocess.check_output(["nmap", "-sPn", "172.23.42.1-254"], universal_newlines=True)
		current_users = []
		for line in scan_result.split("\n"):
			words = line.split()
			if len(words) >= 2:
				if words[0] == "MAC":
					mac_address = words[2].upper()
					if mac_address in macs.keys():
						current_users.append(macs[mac_address])

		current_users = list(set(current_users)) # Dont duplicate users
		time.sleep(60)


class MyOwnBot(pydle.Client):
	@asyncio.coroutine
	def on_connect(self):
		 yield from self.join('#afra')

	@asyncio.coroutine
	def on_message(self, target, source, message):
		global current_users
		# don't respond to our own messages, as this leads to a positive feedback loop
		if source != self.nickname and (".presence" in message or ".present" in message):
			if len(current_users) == 0:
				m = "Nobody wants to be surveiled."
			else:
				m = "Now at AfRA: " + ", ".join(current_users)
			yield from self.message(target, m)


current_users = []
threading.Thread(target=mac_tester).start()

client = MyOwnBot("pr3s3nce", realname="AfRA attendance bot")
client.run('chat.freenode.net', tls=True, tls_verify=False)


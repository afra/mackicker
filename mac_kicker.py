#!/usr/bin/env python3
#
# MIT
# ciko@afra-berlin.de
import pydle, threading, subprocess, time, asyncio, hashlib, requests, evdev

def mac_tester():
	global current_mac_users, current_rfid_users
	while True:
		# Load the macs. in the loop for auto reload
		macs = {}
		with open("registered_macs", "r") as f:
			for line in f.readlines():
				if len(line.strip()) > 0:
					macs[line.split()[0].upper()] = line.split()[1]

		# Scan for all macs in the current network
		scan_result = subprocess.check_output(["nmap", "-sPn", "172.23.42.1-254"], universal_newlines=True)
		current_mac_users = []
		for line in scan_result.split("\n"):
			words = line.split()
			if len(words) >= 2:
				if words[0] == "MAC":
					mac_address = words[2].upper()
					if mac_address in macs.keys():
						current_mac_users.append(macs[mac_address])

		current_mac_users = list(set(current_mac_users)) # Dont duplicate users

		# If the door is closed, kill all RFID users
		if "LOCKED" in requests.get("http://door:8080/").text:
			current_rfid_users = []

		time.sleep(60)


def find_rfid_user(authcode):
	with open("registered_rfid", "r") as f:
		tokenlines = f.readlines()

	for line in tokenlines:
		if line.split()[0].upper() == hashlib.sha224(authcode.encode()).hexdigest().upper():
			return line.split()[1]

	return None


def rfid_watcher():
	global current_rfid_users
	rfid_reader = evdev.InputDevice('/dev/input/event0')
	print("Connected to RFID Reader")
	current_code = ""
	keys = "XX1234567890XXXXqwertzuiopXXXXasdfghjklXXXXXyxcvbnmXXXXXXXXXXXXXXXXXXXXXXX"

	for event in rfid_reader.read_loop():
		if event.type == 1 and event.value == 1:
			if event.code > len(keys):
				continue

			if keys[event.code] in "0123456789":
				current_code += keys[event.code]
			else:
				rfid_user = find_rfid_user(current_code)
				if rfid_user:
					if rfid_user in current_rfid_users:
						current_rfid_users.remove(rfid_user)
					else:
						current_rfid_users.append(rfid_user)
				
				current_code = ""


class MyOwnBot(pydle.Client):
	@asyncio.coroutine
	def on_connect(self):
		 yield from self.join('#afra')

	@asyncio.coroutine
	def on_message(self, target, source, message):
		global current_mac_users, current_rfid_users

		current_users = list(set(current_mac_users + current_rfid_users))
		# don't respond to our own messages, as this leads to a positive feedback loop
		if source != self.nickname:
			if(".presence" in message or ".present" in message):
				if len(current_users) == 0:
					m = "Nobody wants to be surveilled."
				else:
					m = "Now at AfRA: " + ", ".join(current_users)
				yield from self.message(target, m)
			elif (".clear" in message):
				current_mac_users = []
				current_rfid_users = []


current_mac_users = []
current_rfid_users = []
threading.Thread(target=mac_tester).start()
threading.Thread(target=rfid_watcher).start()

client = MyOwnBot("pr3s3nce", realname="AfRA attendance bot")
client.run('chat.freenode.net', tls=True, tls_verify=False)


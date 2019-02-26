#!/usr/bin/env python3
#
# MIT
# ciko@afra-berlin.de
import asyncio
import datetime
import subprocess
import time
import threading

import evdev
import hashlib
import pydle
import requests

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
		try:
			if "LOCKED" in requests.get("http://door:8080/").text:
				current_rfid_users = []
		except Exception:
			pass # Ignore if the door is dead

		time.sleep(60)


def find_rfid_user(authcode):
	enc_authcode = hashlib.sha224(authcode.encode()).hexdigest().upper()
	with open("registered_rfid", "r") as f:
		tokenlines = f.readlines()

	for line in tokenlines:
		words = line.split()
		if len(words) >= 2:
			if words[0].upper() == enc_authcode:
				return words[1]

	return None


def rfid_watcher():
	global current_rfid_users
	rfid_reader = evdev.InputDevice('/dev/input/event0')
	print("Connected to RFID Reader")
	current_code = ""
	keys = "XX1234567890XXXXqwertzuiopXXXXasdfghjklXXXXXyxcvbnmXXXXXXXXXXXXXXXXXXXXXXX"

	# Read the keys
	for event in rfid_reader.read_loop():
		if event.type == 1 and event.value == 1:  # Keyboard events
			if event.code > len(keys):
				continue

			if keys[event.code] in "0123456789":
				current_code += keys[event.code]
			else:
				rfid_user = find_rfid_user(current_code)
				if not rfid_user:
					continue

				if rfid_user in current_rfid_users:
					current_rfid_users.remove(rfid_user)
					speak("Goodbye {}".format(rfid_user))
				else:
					current_rfid_users.append(rfid_user)
					speak("Welcome {}".format(rfid_user))

				current_code = ""


def speak(text):
	subprocess.run(["pico2wave" ,"--lang", "en-US", "--wave", "/tmp/tts.wav", "\"{}\"".format(text)])
	subprocess.run(["aplay", "-D", "plughw:CARD=Device,DEV=0", "/tmp/tts.wav"])
	subprocess.run(["rm", "/tmp/tts.wav"])


def register_eta(user, message):
	# .eta 10min (arrives in 10 minutes)
	global current_eta_users

	message_parts = message.split()
	if len(message_parts) != 2: return # Skip invalid messages
	if message_parts[0] != ".eta" or "min" not in message_parts[1]: return # Skip non ETA messages

	try:
		until_arrival = datetime.timedelta(minutes=int(message_parts[1].replace("min", "")))
	except TypeError:
		return
	except ValueError:
		return

	arrival_time = datetime.datetime.now() + until_arrival
	current_eta_users.append([user, arrival_time])
	speak("{} will arrive at {}".format(user), arrival_time.strftime("%H %M"))


def get_formatted_eta_users():
	global current_eta_users
	formatted_eta_users = []

	now = datetime.datetime.now()

	for eta_user in current_eta_users:
		if eta_user[1] < now:
			current_eta_users.remove(eta_user)
		else:
			formatted_eta_users.append("{} ({})".format(eta_user[0], eta_user[1].strftime("%H:%M")))

	return formatted_eta_users


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
			if (".presence" in message or ".present" in message):
				formatted_eta_users = get_formatted_eta_users()
				m = ""
				if len(current_users) == 0 and len(formatted_eta_users) == 0:
					m += "Nobody wants to be surveilled."
				if len(current_users) > 0:
					m += "Now at AfRA: " + ", ".join(current_users)
				if len(formatted_eta_users) > 0:
					m += "\nSoon to arrive: " + ", ".join(formatted_eta_users)

				yield from self.message(target, m)
			elif ".eta" in message:
				register_eta(source, message)

			elif ".clear" in message:
				current_mac_users = []
				current_rfid_users = []
				current_eta_users = []


	@asyncio.coroutine
	def on_private_message(self, source, message):
		if ".eta" in message:
			register_eta(source, message)


current_mac_users = []
current_rfid_users = []
current_eta_users = []
threading.Thread(target=mac_tester).start()
threading.Thread(target=rfid_watcher).start()

client = MyOwnBot("pr3s3nce", realname="AfRA attendance bot")
client.run('chat.freenode.net', tls=True, tls_verify=False)

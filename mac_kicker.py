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
from rpi_ws281x import *


def mac_tester():
	global current_mac_users, current_rfid_users
	while True:
		# Load the macs. in the loop for auto reload
		macs = {}
		with open("registered_macs", "r") as f:
			for line in f.readlines():
				if len(line.strip()) >= 2:
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

		# If the door is closed, kill all RFID and IRC users
		try:
			if "LOCKED" in requests.get("http://door:8080/").text:
				current_rfid_users = []
				current_irc_users = []
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
					color_rotate(Color(255, 0, 0))
					speak("Goodbye {}".format(rfid_user))
				else:
					current_rfid_users.append(rfid_user)
					color_rotate(Color(0, 255, 0))
					speak("Welcome {}".format(rfid_user))

				current_code = ""

        
def register_here(nick):
	global current_irc_users
	if nick not in current_irc_users:
		current_irc_users.append(nick)
		color_rotate(Color(0, 255, 0))
		speak("Welcome {}".format(nick))


def register_gone(nick):
	global current_irc_users
	if nick in current_irc_users:
		current_irc_users.remove(nick)
		color_rotate(Color(255, 0, 0))
		speak("Goodbye {}".format(nick))

    
def speak(text):
	threading.Thread(target=t_speak, args=(text,)).start()


def t_speak(text):
	subprocess.run(["pico2wave" ,"--lang", "en-US", "--wave", "/tmp/tts.wav", "\"{}\"".format(text)])
	subprocess.run(["aplay", "-D", "plughw:CARD=Device,DEV=0", "/tmp/tts.wav"])
	subprocess.run(["rm", "/tmp/tts.wav"])


def register_eta(user, message):
	# .eta 10min (arrives in 10 minutes)
	global current_eta_users

	message_parts = message.split()
	if len(message_parts) != 2: return False  # Skip invalid messages
	if "min" not in message_parts[1]: return False  # Skip non ETA messages

	try:
		until_arrival = datetime.timedelta(minutes=int(message_parts[1].replace("min", "")))
	except TypeError:
		return False
	except ValueError:
		return False

	arrival_time = datetime.datetime.now() + until_arrival
	current_eta_users.append([user, arrival_time])
	speak("{} will arrive at {}".format(user, arrival_time.strftime("%H %M")))
	return True


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


def self_register_mac(nick, message):
	message_parts = message.split()
	if len(message_parts) != 3: return False# Skip invalid messages
	mac = message_parts[2]
	if len(mac.split(":")) != 6 or len(mac) != 17: return False # Skip non-Macs

	with open("registered_macs", "a") as f:
		f.write("\n" + mac + " " + nick)

	return True


def self_remove_mac(nick, message):
	message_parts = message.split()
	if len(message_parts) != 3: return False  # Skip invalid messages
	mac = message_parts[2]
	if len(mac.split(":")) != 6 or len(mac) != 17: return False # Skip non-Macs

	with open("registered_macs", "r") as f:
		mac_lines = f.readlines()

	with open("registered_macs", "w") as f:
		for mac_line in mac_lines:
			if mac.upper() not in mac_line.upper():
				f.write(mac_line)

	return True


def color_rotate(colors, rotations=1):
	threading.Thread(target=t_color_rotate, args=(colors, rotations,)).start()


def t_color_rotate(colors, rotations):
    for i in range(0, strip.numPixels()):
        strip.setPixelColor(i, colors)
        strip.setPixelColor((i+1)%LED_COUNT, Color(0,0,0))
        strip.show()
        time.sleep(0.1)

    for i in range(1, strip.numPixels()):
        strip.setPixelColor(i, Color(0,0,0))
        strip.show()
        time.sleep(0.1)


class MyOwnBot(pydle.Client):
	@asyncio.coroutine
	def on_connect(self):
		 yield from self.join('#afra')


	@asyncio.coroutine
	def on_message(self, target, source, message):
		global current_mac_users, current_rfid_users, current_eta_users, current_irc_users

		current_users = list(set(current_mac_users + current_rfid_users + current_irc_users))
		# don't respond to our own messages, as this leads to a positive feedback loop
		if source != self.nickname:
			if message.startswith(".presence") or message.startswith(".present"):
				formatted_eta_users = get_formatted_eta_users()
				if len(current_users) == 0 and len(formatted_eta_users) == 0:
					yield from self.message(target, "Nobody wants to be surveilled.")
				elif len(current_users) > 0:
					yield from self.message(target, "Now at AfRA: " + ", ".join(current_users))

				if len(formatted_eta_users) > 0:
					yield from self.message(target, "Soon to arrive: " + ", ".join(formatted_eta_users))

			elif message.startswith(".eta"):
				register_eta(source, message)

			elif message.startswith(".here"):
				register_here(source)
			elif message.startswith(".gone"):
				register_gone(source)

			elif message.startswith(".clear"):
				current_mac_users = []
				current_rfid_users = []
				current_eta_users = []


	@asyncio.coroutine
	def on_private_message(self, target, source, message):
		if message.startswith(".eta"):
			if register_eta(source, message):
				yield from self.message(source, "Got it, see you")
			else:
				yield from self.message(source, "Sorry, I did not understand this. Please use: .eta XXmin")
		elif message.startswith(".here"):
			register_here(source)
			yield from self.message(source, "Welcome, you can log out via .gone")
		elif message.startswith(".gone"):
			register_gone(source)
			yield from self.message(source, "Goodbye")
		elif message.startswith(".register mac"):
			if self_register_mac(source, message):
				yield from self.message(source, "MAC registered, the update can take up to 1 minute")
			else:
				yield from self.message(source, "Sorry, I did not understand this. Please use: .register mac MAC_ADDRESS")
		elif message.startswith(".remove mac"):
			if self_remove_mac(source, message):
				yield from self.message(source, "MAC removed, the update can take up to 1 minute")
			else:
				yield from self.message(source, "Sorry, I did not understand this. Please use: .remove mac MAC_ADDRESS")
		else:
			yield from self.message(source, "Sorry, I did not understand. Reference: https://www.afra-berlin.de/dokuwiki/doku.php")


current_mac_users = []
current_rfid_users = []
current_eta_users = []
current_irc_users = []
threading.Thread(target=mac_tester).start()
threading.Thread(target=rfid_watcher).start()

# LED strip configuration:
LED_COUNT      = 16      # Number of LED pixels.
LED_PIN        = 10      # GPIO pin connected to the pixels (must support PWM!).
LED_CHANNEL    = 1       # PWM Channel must correspond to chosen LED_PIN PWM!
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 5       # DMA channel to use for generating signal (try 5)
LED_BRIGHTNESS = 100      # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)

strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS)
strip.begin()

client = MyOwnBot("pr3s3nce", realname="AfRA attendance bot")
client.run('chat.freenode.net', tls=True, tls_verify=False)

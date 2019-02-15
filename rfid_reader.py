#!/usr/bin/env python3
import evdev, requests, hashlib

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
                        sha224_code = hashlib.sha224(current_code.encode()).hexdigest()
                        print(sha224_code)
                        current_code = ""
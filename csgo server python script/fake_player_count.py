#!/usr/bin/env python
# -*- coding: utf-8 -*-

import socket
import binascii
from scapy.all import *

gData = "ffff ffff "\
		"4911 5b47 4552 5d5b 5469 636b 3132 385d "\
		"5b44 7573 745f 324f 6e6c 795d 2043 5359 "\
		"532d 5365 7276 6572 0064 655f 6475 7374 "\
		"3200 6373 676f 0043 6f75 6e74 6572 2d53 "\
		"7472 696b 653a 2047 6c6f 6261 6c20 4f66 "\
		"6665 6e73 6976 6500 da02 0010 0064 6c00 "\
		"0131 2e33 342e 362e 3900 b187 6903 4c3d "\
		"b517 1440 0165 6d70 7479 2c64 7573 745f "\
		"322c 6765 722c 7469 636b 3132 382c 7365 "\
		"6375 7265 00da 0200 0000 0000 00"
gData = gData.replace(' ', '')

def answerPacket(addr):
	global gSocket
	global gData
	gData2 = gData.replace('G', str(9))
	p = IP(dst=addr[0], src="137.226.59.154")/UDP(sport=27015, dport=addr[1])/gData2.decode("hex")
	p.show()
	hexdump(p)
	send(p)


UDP_IP = "" # empty=all
UDP_PORT = 10101

sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP
sock.bind((UDP_IP, UDP_PORT))

while True:
    data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
    print "received message:", binascii.hexlify(data)
    print "answering it..."
    answerPacket(addr)
    print "done"
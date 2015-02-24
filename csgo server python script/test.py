#!/usr/bin/env python
# -*- coding: utf-8 -*-

import socket
import binascii
from random import randint
from scapy.all import *

# See https://developer.valvesoftware.com/wiki/Server_queries#A2S_INFO

gPlayers = {('Destr0ya', 0x00000000, 0xb0d33643), ('HexiHexi', 0x000000A0, 0xb0d32641), ('[RTS]ProNoob', 0x00000000, 0xb0d32643)}
# Note: max 9 players atm
gPlayerNumber = "0"+str(len(gPlayers))

gData54 = "ffff ffff 4911 205b 4745 525d 5b44 5553"\
		"545f 3220 4f4e 4c59 5d5b 5449 434b 2031 "\
		"3238 5d48 4621 0064 655f 6475 7374 3200 "\
		"6373 676f 0043 6f75 6e74 6572 2d53 7472 "\
		"696b 653a 2047 6c6f 6261 6c20 4f66 6665 "\
		"6e73 6976 6500 da02 0G0c 0064 6c00 0131 "\
		"2e33 342e 362e 3900 a187 6966 6e71 7579 "\
		"2c21 2c2a 2c31 3238 2c61 7770 2c63 6173 "\
		"7561 6c2c 6373 676f 2c64 655f 6475 7374 "\
		"322c 6465 7574 7363 682c 6472 6f70 732c "\
		"6765 726d 616e 2c73 6563 7572 6500 da02 "\
		"0000 0000 0000"
gData54 = gData54.replace(' ', '')

# G: number of players whose information was gathered
# H: Index of player chunk starting from 0.
# I Name of the player.
# J: Player's score (usually "frags" or "kills".) 
# K: Time (in seconds) player has been connected to the server.
gData55a = "ffff ffff 44 GG"
gData55b = "HH IIIIIIII JJJJJJJJ KKKKKKKK"
gData55a = gData55a.replace(' ', '')
gData55b = gData55b.replace(' ', '')

# dict of tuples (ip, challengeNr)
gChallengeNumbers = {}
gChallengeCounter = 0xb138d80a # from some packet i inspected

def answerPacket54(addr):
	global gPlayers, gSocket, gData54
	gData2 = gData54.replace("G", str(len(gPlayers)))
	# 178.63.73.38
	p = IP(dst=addr[0], src="178.63.73.38")/UDP(sport=27015, dport=addr[1])/gData2.decode("hex")
	p.show()
	hexdump(p)
	send(p)

def answerPacket55(data, addr):
	global gSocket
	challengeNumber = ""
	data = ""
	# playerName, score, time
	

	for i in range(10,17):
        challengeNumber += data[i]
    if challengeNumber = "00000000":
    	# challenge number request
    	gChallengeCounter++
    	gChallengeNumbers[addr[0]] = gChallengeCounter
    	data = "ffffffff" + challengeNumber
	else:
		#  A2S_PLAYER request
		# ignore challenge number...
		data = gData55a.replace("GG", gPlayerNumber)

		

	p = IP(dst=addr[0], src="178.63.73.38")/UDP(sport=27015, dport=addr[1])/data.decode("hex")
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
    if data[8] == 5 && data[9] == 4: # A2S_INFO
    	answerPacket54(addr)
    elif data[8] == 5 && data[9] == 5: # A2S_PLAYER
    	answerPacket55(data, addr)
    else
    	print "Unknown packet :-("
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import socket
import binascii
from scapy.all import *

gData = "ffff ffff 4911 "\
                "203e 3e3e 3d3d 3e3e 3e20 4455 5354 "\
                "3220 4f4e 4c59 203c 3d3d 3e20 4a4f 494e "\
                "204e 4f57 203c 3c3c 3d3d 3c3c 3c00 6465 "\
                "5f64 7573 7432 0063 7367 6f00 436f 756e "\
                "7465 722d 5374 7269 6b65 3a20 476c 6f62 "\
                "616c 204f 6666 656e 7369 7665 00da 020G "\
                "1000 646c 0001 312e 3334 2e37 2e30 00b1 "\
                "8769 07c0 f7aa 2514 4001 656d 7074 792c "\
                "6475 7374 5f32 2c67 6572 2c74 6963 6b31 "\
                "3238 2c73 6563 7572 6500 da02 0000 0000 "\
                "0000"
gData = gData.replace(' ', '')

def answerPacket(addr):
        global gSocket
        global gData
        gData2 = gData.replace('G', str(3))
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

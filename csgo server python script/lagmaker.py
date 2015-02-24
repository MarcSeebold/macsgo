#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
import logging
import urllib2
import json
import re

from subprocess import call

# Config - Begin
gLogFile = "/home/marc/steamcmd/games/csgo/csgo/console.log"
gSleepInterval = 1.0
# Network device
gDev = "eth0"
# Jitter value (must not be 0!)
gJitter = 1
# How often to adjust the artificial lag (seconds)?
gArtLagInterval = 2
# Maximum lag (real lag + artificial lag)
gLagMax = 90
# Steam API key
gSteamAPIKey = "5302BC196B58F79673F4DD58AF5CCAA5"
# Log level (file and console)
gLogLevel = logging.DEBUG
# Config - End

# Global Vars
# Steam UserStatsUrl
gSteamAPIURL = "http://api.steampowered.com/ISteamUserStats/GetUserStatsForGame/v0002/?appid=730&key={}&steamid={}"
# Cache for players latency
gLatencies = {}
# Total time player cache
gTotalTimePlayed = {}
# Current artificial lag for every player
gLatenciesArt = {}
# Last time the artificial lag has been modified for every ip
gLatencyLastEdit = {}
# TC: classid for every ip
gTcIpIdMap = {}
# TC: All free class ids (store them to recycle)
gTcFreeClassIDS = []
# Current max lag of all players
gLagCurrMax = 0

# Log errors
logging.basicConfig(filename='lagmaker.log',level=gLogLevel)
# Log to console by https://docs.python.org/2/howto/logging-cookbook.html
# define a Handler which writes INFO messages or higher to the sys.stderr
console = logging.StreamHandler()
console.setLevel(gLogLevel)
# set a format which is simpler for console use
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
# tell the handler to use this format
console.setFormatter(formatter)
# add the handler to the root logger
logging.getLogger('').addHandler(console)


# Traffic control stuff
def tcInit():
    "Initialize linux traffic control queues"
    global gDev, gTcFreeClassIDS, gTcIpIdMap, gLatencies, gLatenciesArt
    global gLatencyLastEdit, gLagCurrMax
    ok = True
    # main queue
    ok &= (0 == call(["tc", "qdisc", "add", "dev", gDev, "handle", "1:", "root", "htb"]))
    # main class
    ok &= (0 == call(["tc", "class", "add", "dev", gDev, "parent", "1:", "classid", "1:1", "htb", "rate", "100Mbps"]))
    gTcFreeClassIDS = range(10, 99)
    gTcIpIdMap = {}
    gLatencies = {}
    gLatenciesArt = {}
    gLatencyLastEdit = {}
    gLagCurrMax = 0
    if ok:
        logging.info("Successfully initialized tc.")
    else:
        logging.error("Failed to initialize tc.")
    return ok


def tcDestroy():
    "Delete all qdiscs, filters and classes"
    ok = (0 == call(["tc", "qdisc", "del", "dev", gDev, "root"]))
    if ok:
        logging.info("Successfully de-initialized tc.")
    else:
        logging.error("Failed to de-initialize tc.")
    return ok    


def tcSetDelay(ip, delayMs):
    "Set delay for a specific ip address. It will automatically generate a traffic command qdisc, class and a filter if not yet existant."
    global gTcIpIdMap, gTcFreeClassIDS, gDev, gJitter
    ok = True
    if ip not in gTcIpIdMap:
        "No tc stuff created yet. Do it!"
        newID = gTcFreeClassIDS.pop()
        cmd1 = ["tc", "class", "add", "dev", gDev, "parent", "1:1", "classid", "1:"+str(newID), "htb", "rate", "100Mbps"]
        cmd2 = ["tc", "qdisc", "add", "dev", gDev, "parent", "1:"+str(newID), "handle", str(newID)+":", "netem", "delay", str(delayMs)+"ms", str(gJitter)+"ms", "distribution", "normal"]
        cmd3 = ["tc", "filter", "add", "dev", gDev, "protocol", "ip", "parent", "1:", "prio", "1", "u32", "match", "ip", "dst", ip, "flowid", "1:"+str(newID)]
        ok &= (0 == call(cmd1))
        ok &= (0 == call(cmd2))
        ok &= (0 == call(cmd3))
        if ok:
            gTcIpIdMap[ip] = newID
            return True
        else:
            logging.error("Failed to set lag. Commands: ")
            logging.error(cmd1)
            logging.error(cmd2)
            logging.error(cmd3)
            gTcFreeClassIDS.append(newID)
            return False
    else:
        currID = gTcIpIdMap[ip]
        logging.debug(["tc", "qdisc", "change", "dev", gDev, "parent", "1:"+str(currID), "handle", str(currID)+":", "netem", "delay", str(delayMs)+"ms", str(gJitter)+"ms", "distribution", "normal"])
        ok &= (call(["tc", "qdisc", "change", "dev", gDev, "parent", "1:"+str(currID), "handle", str(currID)+":", "netem", "delay", str(delayMs)+"ms", str(gJitter)+"ms", "distribution", "normal"]) == 0)
        return ok


# Logfile parsing
def getTimeDiff(timeA, timeB):
    "Get the time difference of two timestamps in seconds (B-A)"
    diff = 0
    splitsA = timeA.split(':')
    splitsB = timeB.split(':')
    # hours
    diff += 60*60*(int(splitsB[0])-int(splitsA[0]))
    # minutes
    diff += 60*(int(splitsB[1])-int(splitsA[1]))
    # seconds
    diff += int(splitsB[2])-int(splitsA[2])
    return diff


# src: https://github.com/N0S4A2/Steam-ID-Converter/blob/master/SteamIDConverter.py
def convertSteamID(steamID):
    "Convert a steam id to community id"
    steamIDBase = 76561197960265728
    steamIDParts = re.split(":", steamID)
    communityID = int(steamIDParts[2]) * 2
    if steamIDParts[1] == "1":
        communityID += 1
    communityID += steamIDBase
    return communityID


def updateCurrMaxLag():
    "Updates the gLagCurrMax variable (and returns it)"
    global gLagCurrMax, gLatencies, gLatenciesArt, gLagMax
    gLagCurrMax = 0
    for currId in gLatencies:
        if currId in gLatenciesArt:
            realLag = gLatencies[currId] - gLatenciesArt[currId]
            if gLagCurrMax < realLag:
                gLagCurrMax = realLag
    gLagCurrMax = max(gLagCurrMax, 0)
    gLagCurrMax = min(gLagCurrMax, gLagMax)
    return gLagCurrMax


# Defines
PARSE_DATE = 1
PARSE_TIME = 3
PARSE_COUNTRY = 6
PARSE_IP = 8
PARSE_STEAMID = 10
PARSE_LAG = 24
def getCSGOPlayTime(steamid):
    global gSteamAPIKey, gSteamAPIURL, gTotalTimePlayed
    if steamid in gTotalTimePlayed: #caching
        res = gTotalTimePlayed[steamid]
        if res != 0:
            return gTotalTimePlayed[steamid]

    logging.debug("getCSGOPlayTime cache miss. Requesting total_time_played for %s", steamid)
    try:
        response = urllib2.urlopen(gSteamAPIURL.format(gSteamAPIKey, steamid))
    except urllib2.HTTPError:
        logging.error("getCSGOPlayTime: HTTP error.")
        return 0
    htmlData = response.read()
    jsonData = json.loads(htmlData)
    try:
        stats = jsonData['playerstats']['stats']
        for currStat in stats:
            if currStat['name'] == "total_time_played":
                res = int(currStat['value'])
                logging.debug("getCSGOPlayTime response for %s: %i", steamid, res)
                gTotalTimePlayed[steamid] = res
                return res
    except IndexError:
        logging.error("getCSGOPlayTime: Index out of bounds raised.")
        return 0
    return 0


def parseLatencyInfo(line):
    "Parse a line of latency information"
    global gLatencies, gLatenciesArt, gArtLagInterval, gLatencyLastEdit, gLagCurrMax
    splits = line.split(' ')

    if len(splits) != 24+1 or splits[4] != "[latencytolog.smx]":
        return

    currIP = splits[PARSE_IP]
    if currIP not in gLatencyLastEdit:
        gLatencyLastEdit[currIP] = "00:00:00"
    lastTime = gLatencyLastEdit[currIP]
    currTime = splits[PARSE_TIME][:-1] # remove last char: 01:23:45: -> 01:23:45
    if (abs(getTimeDiff(currTime, lastTime)) < gArtLagInterval):
        return # only adjust lag every X seconds
    gLatencyLastEdit[currIP] = currTime

    steamid = splits[PARSE_STEAMID]
    if steamid not in gLatencies:  # make sure an old value exists for diff
        gLatencies[steamid] = int(0)
        gLatenciesArt[steamid] = int(0)
    logging.debug("{} {}".format(splits[PARSE_DATE], splits[PARSE_TIME]))
    logging.debug( "{} {} {}".format(splits[PARSE_COUNTRY], currIP, steamid))
    lag = int(splits[PARSE_LAG])
    logging.debug( "lag: {}ms. diff: {}ms".format(lag, abs(lag-gLatencies[steamid])))
    gLatencies[steamid] = int(lag)

    # artificial lag
    currRealLag = gLatencies[steamid] - gLatenciesArt[steamid]
    if currRealLag < 0:
        currRealLag = 0
    artLag = gLagCurrMax - currRealLag
    if artLag < 1:
        artLag = 1
    logging.debug( "Out: " + str(int(float(splits[12])*1000)))
    logging.debug( "In: " + str(int(float(splits[14])*1000)))
    logging.debug( "both: " + str(int(float(splits[16])*1000)))
    logging.debug( "avg Out: " + str(int(float(splits[18])*1000)))
    logging.debug( "avg In: " + str(int(float(splits[20])*1000)))
    logging.debug( "avg both: " + str(int(float(splits[22])*1000)))
    logging.debug( "real ping: " + str(int(splits[24])))
    gLatenciesArt[steamid] = artLag
    tcSetDelay(currIP, artLag)

    csgoPlayTime = getCSGOPlayTime(convertSteamID(steamid))
    logging.info('IP: %s STEAMID: %s REALLAG: %i ARTLAG: %i PLAYTIME: %i', currIP, steamid, int(currRealLag), int(artLag), csgoPlayTime)


def parseDisconnection(line):
    "Called whenever a disconnection is detected"
    splits = line.split(' ')
    if len(splits) < 5:
        return
    splits2 = splits[4].split('<')
    if len(splits2) < 3:
        return
    steamid = splits2[2][:-1]
    if steamid != "BOT":
        if steamid in gLatencies:
            del gLatencies[steamid]
        if steamid in gLatenciesArt:
            del gLatenciesArt[steamid]
        logging.info('STEAMID: %s LEFT_THE_GAME', steamid)

def parseNewGame(line):
    "Called whenever a new game (not round!) has started"
    logging.info('NEW ROUND')
    # Re-Init TC, so old entries get deleted
    tcDestroy()
    tcInit()


def parseLine(line):
    "Parse a line"
    if "[latencytolog.smx]" in line:
        parseLatencyInfo(line)
    elif "disconnected" in line:
        parseDisconnection(line)
    elif "Loading map" in line:
        parseNewGame(line)


# http://lethain.com/tailing-in-python/
def readlines_then_tail(fin):
    "Iterate through lines and then tail for further lines."
    while True:
        line = fin.readline()
        if line:
            yield line
        else:
            tail(fin)


def update():
    "Stuff called every gSleepInterval seconds"
    updateCurrMaxLag()

def tail(fin):
    "Listen for new lines added to file."
    while True:
        where = fin.tell()
        line = fin.readline()
        if not line:
            time.sleep(gSleepInterval)
            update()
            fin.seek(where)
        else:
            yield line


def main():
    if os.geteuid() != 0: #or maybe if not os.geteuid()
        logging.error("This script must be run as root.")
        sys.exit(1)
    tcDestroy(); # just to be sure
    tcInit()
    try:
        with open(gLogFile, 'r') as fin:
            # Skip to last line
            logging.debug("Skipping old lines...")
            for line in fin:
                pass
            logging.debug("Done")
            for line in tail(fin):
                parseLine(line.strip())
    except KeyboardInterrupt:
        logging.debug("Bye")
    tcDestroy()


if __name__ == '__main__':
    main()

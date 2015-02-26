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
gLogFile = "/home/marc/steamcmd/games/csgo/csgo/addons/sourcemod/logs/latencies.log"
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
# Max number of rounds
gMaxRounds = 9
# Config - End

# Global Vars
# Steam UserStatsUrl
gSteamAPIURL = "http://api.steampowered.com/ISteamUserStats/GetUserStatsForGame/v0002/?appid=730&key={}&steamid={}"
# Cache for players latency. key: steamid, value: latency
gLatencies = {}
# Enable/Disable Artificial lag for specific players (e.g., when they are dead). Key: steamid, value: bool
gPlayersWithoutLag = {}
# Totally enable/disable artifical lag
gEnableArtLag = False
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
# Current Round number
gRound = 0

# Log errors
logging.basicConfig(filename='lagmaker.log',level=gLogLevel, format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s', datefmt='%m-%d %H:%M:%S')
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
    global gTcIpIdMap, gTcFreeClassIDS, gDev, gJitter, gEnableArtLag
    if gEnableArtLag == False:
        return True
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
def convertStringSteamID(steamID):
    "Convert a STEAM_0:X:Y steam id to community id"
    steamIDBase = 76561197960265728
    steamIDParts = re.split(":", steamID)
    communityID = int(steamIDParts[2]) * 2
    if steamIDParts[1] == "1":
        communityID += 1
    communityID += steamIDBase
    return communityID

def convert32SteamID(steamID):
    res = 76561197960265728
    res += long(steamID)
    return res


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


def getCSGOPlayTime(steamid):
    global gSteamAPIKey, gSteamAPIURL, gTotalTimePlayed
    if steamid in gTotalTimePlayed: #caching
        res = gTotalTimePlayed[steamid]
        if res != 0:
            return gTotalTimePlayed[steamid]

    logging.debug("getCSGOPlayTime cache miss. Requesting total_time_played for %s", steamid)
    try:
        response = urllib2.urlopen(gSteamAPIURL.format(gSteamAPIKey, convert32SteamID(steamid)))
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


# Defines
PARSE_COUNTRY = 2
PARSE_IP = 4
PARSE_STEAMID = 6
PARSE_LAG = 20
def parseLatencyInfo(line, date, time):
    "Parse a line of latency information"
    global gLatencies, gLatenciesArt, gArtLagInterval, gLatencyLastEdit, gLagCurrMax, gPlayersWithoutLag
    splits = line.split(' ')

    assert(len(splits) == 21)
    assert(splits[0] == "LATENCY:")

    if gEnableArtLag == False:
        return

    currIP = splits[PARSE_IP]
    if currIP not in gLatencyLastEdit:
        gLatencyLastEdit[currIP] = "00:00:00"
    lastTime = gLatencyLastEdit[currIP]
    if (abs(getTimeDiff(time, lastTime)) < gArtLagInterval):
        return # only adjust lag every X seconds
    gLatencyLastEdit[currIP] = time

    steamid = splits[PARSE_STEAMID]
    if steamid not in gPlayersWithoutLag: # default: on
        gPlayersWithoutLag[steamid] = False

    # Lag can be disabled for some players
    if gPlayersWithoutLag[steamid] == True:
        tcSetDelay(currIP, 1)
        return

    if steamid not in gLatencies:  # make sure an old value exists for diff
        gLatencies[steamid] = int(0)
        gLatenciesArt[steamid] = int(0)
    logging.debug("{} {}".format(date, time))
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
    logging.debug( "Out: " + str(int(float(splits[8])*1000)))
    logging.debug( "In: " + str(int(float(splits[10])*1000)))
    logging.debug( "both: " + str(int(float(splits[12])*1000)))
    logging.debug( "avg Out: " + str(int(float(splits[14])*1000)))
    logging.debug( "avg In: " + str(int(float(splits[16])*1000)))
    logging.debug( "avg both: " + str(int(float(splits[18])*1000)))
    logging.debug( "real ping: " + str(int(splits[20])))
    gLatenciesArt[steamid] = artLag
    tcSetDelay(currIP, artLag)

    #csgoPlayTime = getCSGOPlayTime(convertSteamID(steamid))
    csgoPlayTime = getCSGOPlayTime(steamid)
    logging.info('IP: %s STEAMID: %s REALLAG: %i ARTLAG: %i PLAYTIME: %i', currIP, steamid, int(currRealLag), int(artLag), csgoPlayTime)


def parseDisconnect(line):
    "Called whenever a disconnection is detected"
    splits = line.split(' ')
    assert(len(splits) == 3)
    assert(splits[0] == "DISCONNECT")

    steamid = splits[2]
    if steamid > 0:
        if steamid in gLatencies:
            del gLatencies[steamid]
        if steamid in gLatenciesArt:
            del gLatenciesArt[steamid]
        logging.info('%s has left the game' % steamid)

def parseMatchEnd(line):
    "Called whenever a new game (not round!) has started"
    global gEnableArtLag
    logging.info('MATCHEND')
    # Disable TC, so old entries get deleted and players do not notice the lag in the scoreboard
    gEnableArtLag=False
    tcDestroy()

def parseConnect(line):
    "A new player has connected"
    # intentionally left empty

def parseRoundStart(line):
    "A new round has started"
    global gRound, gEnableArtLag, gPlayersWithoutLag
    gPlayersWithoutLag = {}
    splits = line.split(" ")
    assert(len(splits) == 2)
    gRound = int(splits[1])
    if gRound == 7: # Enable art. lag in last 3th of the game
        tcInit()
        gEnableArtLag=True
        logging.info("Begin of last 3th of the game. Enabled art. lag.")
    elif gRound == 1:
        # disable lag... just to be sure
        tcDestroy()
        gEnableArtLag=False
        logging.info("First round. Disabling artificial lag.")
    logging.info("Round %i has started" % int(gRound))

def parseRoundEnd(line):
    "A round has ended"
    global gRound
    # intentionally left empty
    logging.info("Round %i has ended" % int(gRound))

def parseBotTakeover(line):
    "A player took over control of a bot"
    global gPlayersWithoutLag
    # Re-enable lag for this player since he is part of the game again
    steamid = line.split(" ")[1]
    gPlayersWithoutLag[steamid]=False
    logging.info("BotTakeover by %s" % steamid)


def parsePlayerDead(line):
    "A player has been killed"
    global gPlayersWithoutLag
    # Disable art lag for dead players (so they do not notice when looking in the scoreboard)
    splits = line.split(" ")
    assert(len(splits) == 9)
    steamidVictim = splits[2]
    gPlayersWithoutLag[steamidVictim]=True
    logging.info("Player killed. Victim: %s" % steamidVictim)

def parseLine(line):
    "Parse a line"
    splits = line.split("[latencytolog.smx]")
    # parse time and date
    dateAndTime = splits[0].split(" ")
    time = dateAndTime[3][:-1]
    date = dateAndTime[1]
    line = splits[1]
    while line[0] == ' ': # remove leading blanks
        line = line[1:]
    
    if line.startswith("DISCONNECT"):
        parseDisconnect(line)
    elif line.startswith("CONNECT"):
        parseConnect(line)
    elif line.startswith("MATCHEND"):
        parseMatchEnd(line)
    elif line.startswith("ROUNDSTART"):
        parseRoundStart(line)
    elif line.startswith("ROUNDEND"):
        parseRoundEnd(line)
    elif line.startswith("BOTTAKEOVER"):
        parseBotTakeover(line)
    elif line.startswith("PLAYERDEAD"):
        parsePlayerDead(line)
    elif line.startswith("LATENCY"):
        parseLatencyInfo(line, date, time)
    else:
        print "Unknown line. Ignoring it... Line: " + line

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

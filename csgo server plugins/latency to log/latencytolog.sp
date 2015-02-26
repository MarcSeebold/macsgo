#include <sourcemod>
#include <geoip>
#include <clients>
 
public Plugin:myinfo =
{
	name = "LatencyToLog",
	author = "Marc Seebold",
	description = "Writes the users latencies to the logfile.",
	version = "1.0",
	url = ""
};

new bool:logDebugInfo = false; // Log some logDebugInfo info
new frameSkipper;
new String:logfile[255];
new bool:hasIntermissionStarted = false;
new roundNumber = 0; // first real round will be "1"
 
public getRealPlayerCount()
{
    new res = 0;
        for (new i = 1; i <= GetMaxClients(); i++)
            if (IsClientInGame(i) && !IsFakeClient(i))
                res++;
    return res;
}

public OnPluginStart()
{
    BuildPath(Path_SM, logfile, sizeof(logfile), "logs/latencies.log");
    HookEvent("cs_intermission", Event_Intermission);
    HookEvent("announce_phase_end", Event_PhaseEnd);
    HookEvent("round_end",Event_RoundEnd);
    HookEvent("round_start",Event_RoundStart);
    HookEvent("player_death",Event_PlayerDeath);
    HookEvent("bot_takeover",Event_BotTakeover);
}

public OnClientDisconnect(int client)
{
    new players = getRealPlayerCount();
    if (logDebugInfo)
        LogToFile(logfile, "logDebugInfo OnClientDisconnect %i %i", roundNumber, players);
    new steamid = GetSteamAccountID(client, false);
    if (steamid != 0)
        LogToFile(logfile, "DISCONNECT STEAMID: %i", steamid)
    if (players == 0)
        roundNumber = 0
}

public OnClientPutInServer(int client)
{
    if (logDebugInfo)
        LogToFile(logfile, "logDebugInfo OnClientPutInServer %i", roundNumber);
    new steamid = GetSteamAccountID(client, false);
    if (steamid != 0)
        LogToFile(logfile, "CONNECT STEAMID: %i", steamid)
}

public Event_Intermission(Handle:event, const String:name[], bool:dontBroadcast)
{
    if (logDebugInfo)
        LogToFile(logfile, "logDebugInfo Event_Intermission %i", roundNumber);
    hasIntermissionStarted = true;
}

// src: https://github.com/powerlord/sourcemod-mapchooser-extended/blob/master/addons/sourcemod/scripting/mapchooser_extended.sp
public Event_PhaseEnd(Handle:event, const String:name[], bool:dontBroadcast)
{
    if (logDebugInfo)
        LogToFile(logfile, "logDebugInfo Event_PhaseEnd %i", roundNumber);
    /* announce_phase_end fires for both half time and the end of the map, but intermission fires first for end of the map. */
    if (hasIntermissionStarted)
    {
        LogToFile(logfile, "MATCHEND");
        roundNumber = -2;
    }
}

public Event_RoundStart(Handle:event, const String:name[], bool:dontBroadcast)
{
    if (logDebugInfo)
        LogToFile(logfile, "logDebugInfo Event_RoundStart %i", roundNumber);
    roundNumber++;
    if (roundNumber > 0)
        LogToFile(logfile, "ROUNDSTART: %i", roundNumber);
}

public Event_RoundEnd(Handle:event, const String:name[], bool:dontBroadcast)
{
    if (logDebugInfo)
        LogToFile(logfile, "logDebugInfo Event_RoundEnd %i", roundNumber);
    if (roundNumber > 0)
        LogToFile(logfile, "ROUNDEND: %i", roundNumber);
}

public Event_BotTakeover(Handle:event, const String:name[], bool:dontBroadcast)
{
    if (logDebugInfo)
        LogToFile(logfile, "logDebugInfo Event_BotTakeover %i", roundNumber);
    if (roundNumber <= 0)
        return;

    new userId = GetEventInt(event, "userid");    
    new user = GetClientOfUserId(userId);
    new steamId = GetSteamAccountID(user, false);
    LogToFile(logfile, "BOTTAKEOVER: %i", steamId);
}

public Event_PlayerDeath(Handle:event, const String:name[], bool:dontBroadcast)
{
    if (logDebugInfo)
        LogToFile(logfile, "logDebugInfo Event_PlayerDeath %i", roundNumber);
    if (roundNumber <= 0)
        return;

    new victimId = GetEventInt(event, "userid");
    new attackerId = GetEventInt(event, "attacker");
    new bool:headshot = GetEventBool(event, "headshot");
    decl String:weapon[64];
    GetEventString(event, "weapon", weapon, sizeof(weapon));

    new victim = GetClientOfUserId(victimId);
    new attacker = GetClientOfUserId(attackerId);
    // bots will have id 0
    new victimSteam = GetSteamAccountID(victim, false);
    new attackerSteam = GetSteamAccountID(attacker, false);

    LogToFile(logfile, "PLAYERDEAD: victim: %i attacker: %i, headshot: %d, weapon: %s", victimSteam, attackerSteam, headshot, weapon);
}

public mathClamp(value, min, max)
{
    if (value < min)
        return min;
    if (value > max)
        return max;
    return value;
}


// src: https://forums.alliedmods.net/archive/index.php/t-226861.html
// however, modified...
public Client_GetFakePing(client, bool:goldSource)
{
    decl ping;
    new Float:latency = GetClientAvgLatency(client, NetFlow_Outgoing);
    new Float:latencyOld = latency;
    decl String:cl_cmdrate[4];
    GetClientInfo(client, "cl_cmdrate", cl_cmdrate, 4);
    new Float:tickRate = GetTickInterval();

    latency -= 0.5 / StringToInt(cl_cmdrate, 10) + tickRate * 1.0;
    if (goldSource)
    {
        latency -= tickRate * 0.5;
    }
    ping = RoundFloat(latency * 1000.0);
    //LogMessage("ping: %i lat: %f latold: %f cmd: %s cmdInt: %i tick: %f", ping, latency, latencyOld, cl_cmdrate, StringToInt(cl_cmdrate, 10), tickRate);
    ping = mathClamp(ping, 5, 1000);
    return ping;
}

public OnGameFrame()
{
    frameSkipper++;
    if (frameSkipper < 100) // Do not log every frame
        return;
    frameSkipper=0;
        
    for (new i = 1; i <= GetMaxClients(); i++)
    {
        if (IsClientInGame(i) && !IsFakeClient(i))
        {
            new Float:out = GetClientLatency(i, NetFlow_Outgoing);
            new Float:inc = GetClientLatency(i, NetFlow_Incoming);
            new Float:both = GetClientLatency(i, NetFlow_Both);
            
            new Float:outavg = GetClientAvgLatency(i, NetFlow_Outgoing);
            new Float:inavg = GetClientAvgLatency(i, NetFlow_Incoming);
            new Float:bothavg = GetClientAvgLatency(i, NetFlow_Both);
            
            //new String:steamid[32];
            //GetClientAuthId(i, AuthId_Steam2, steamid, sizeof(steamid))//GetSteamAccountID(i);
            new steamid = GetSteamAccountID(i, false);
            new String:ip[17];
            GetClientIP(i, ip, 16);
            
            new String:country[4];
            GeoipCode3(ip, country);

            new fakeping = Client_GetFakePing(i, false)
            
            //LogToFile(logfile, "LATENCY: COUNTRY: %s IP: %s STEAMID: %i OUT: %f IN: %f BOTH: %f OUTavg: %f INavg: %f BOTHavg: %f FAKEPING: %i", country, ip, steamid, out, inc, both, outavg, inavg, bothavg, fakeping);
        }
    }  
}
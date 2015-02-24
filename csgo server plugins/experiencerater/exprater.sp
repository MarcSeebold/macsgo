#include <sourcemod>
#include <geoip>
#include <menus>
 
public Plugin:myinfo =
{
	name = "ExperienceRater",
	author = "Marc Seebold",
	description = "Asks the user how his experience was and writes it to a file.",
	version = "1.0",
	url = ""
};

new String:g_logfile[255];
new bool:g_HasIntermissionStarted = false;

public OnPluginStart()
{
    BuildPath(Path_SM, g_logfile, sizeof(g_logfile), "logs/user_ratings.log");
    HookEvent("cs_intermission", Event_Intermission);
    HookEvent("announce_phase_end", Event_PhaseEnd);
}

public OnClientDisconnect(int client)
{
    new steamid = GetSteamAccountID(client, false);
    if (steamid != 0)
        LogToFile(g_logfile, "DISCONNECT STEAMID: %i", steamid)
}

public OnClientConnected(int client)
{
    new steamid = GetSteamAccountID(client, false);
    if (steamid != 0)
        LogToFile(g_logfile, "CONNECT STEAMID: %i", steamid)
}

public Handle_Menu(Handle:menu, MenuAction:action, param1, param2)
{
    if (action == MenuAction_End)
    {
        /* This is called after VoteEnd */
        CloseHandle(menu);
    } 
}

public Event_Intermission(Handle:event, const String:name[], bool:dontBroadcast)
{
    g_HasIntermissionStarted = true;
}

// src: https://github.com/powerlord/sourcemod-mapchooser-extended/blob/master/addons/sourcemod/scripting/mapchooser_extended.sp
public Event_PhaseEnd(Handle:event, const String:name[], bool:dontBroadcast)
{
    /* announce_phase_end fires for both half time and the end of the map, but intermission fires first for end of the map. */
    if (g_HasIntermissionStarted)
    {
        // show voting menu
        new Handle:menu = CreateMenu(Handle_Menu);
        SetVoteResultCallback(menu, Handle_VoteResults);
        SetMenuTitle(menu, "Please rate\n the playability\n on this server.");
        AddMenuItem(menu, "1", "***** Excellent");
        AddMenuItem(menu, "2", "****  Very Good");
        AddMenuItem(menu, "3", "***   Good");
        AddMenuItem(menu, "4", "**    Fair");
        AddMenuItem(menu, "5", "*     Poor");
        SetMenuExitButton(menu, false);
        VoteMenuToAll(menu, 30);
    }
    LogToFile(g_logfile, "Match has ended.");
}

public Handle_VoteResults(Handle:menu, 
            num_votes, 
            num_clients, 
            const client_info[][2], 
            num_items, 
            const item_info[][2])
{
    for (new i=0; i<num_clients; i++)
    {
        new cIdx = client_info[i][VOTEINFO_CLIENT_INDEX];
        new cChoice = client_info[i][VOTEINFO_CLIENT_ITEM];

        new steamid = GetSteamAccountID(cIdx);
        new String:ip[17];
        GetClientIP(cIdx, ip, 16);
        
        new String:country[4];
        GeoipCode3(ip, country);

        LogToFile(g_logfile, "COUNTRY: %s IP: %s STEAMID:%i RATING:%i DEATHS: %i FRAGS: %i TEAM: %i TIME: %f", country, ip, steamid, cChoice+1, GetClientDeaths(cIdx), GetClientFrags(cIdx), GetClientTeam(cIdx), GetClientTime(cIdx));
    }
}
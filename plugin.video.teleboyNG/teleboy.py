
import os, re, sys, base64, datetime
import cookielib, urllib, urllib2, urlparse
import xbmcgui, xbmcplugin, xbmcaddon
import dateutil.parser, dateutil.tz
from mindmade import *
import simplejson

__author__     = "Filippo Labadini"
__copyright__  = "Copyright 2011-2015 mindmade.org, 2015-2017 Labadini F."
__credits__    = [ "Andreas Wetzel", "Roman Haefeli", "Francois Marbot", "reduzent", "stunna", "primaeval", "bruno-briner" ]
__maintainer__ = "Filippo Labadini"
__email__      = ""

#
# constants definition
############################################
PLUGINID = "plugin.video.teleboyNG"

MODE_FAV = "live_fav"
MODE_ALL = "live_all"
MODE_RECS = "recs_ready"
MODE_PLAY = "play_live"
MODE_REPLAY = "play_record"
PARAMETER_KEY_MODE = "mode"
PARAMETER_KEY_STATION = "station"
PARAMETER_KEY_ASSETID = "assetid"

TB_URL = "https://www.teleboy.ch"
IMG_URL = "http://media.cinergy.ch"
API_URL = "http://tv.api.teleboy.ch"
API_KEY = base64.b64decode( "NmNhOTlkZGIzZTY1OWU1N2JiYjliMTg3NDA1NWE3MTFiMjU0NDI1ODE1OTA1YWJhYWNmMjYyYjY0ZjAyZWIzZA==")
COOKIE_FILE = xbmc.translatePath( "special://home/addons/" + PLUGINID + "/resources/cookie.dat")


session_cookie = ''
user_id = ''
plugin_url = sys.argv[0]
plugin_handle = int(sys.argv[1])
plugin_params = sys.argv[2][1:]
plugin_refresh = plugin_url + '?' + plugin_params
settings = xbmcaddon.Addon( id=PLUGINID)
cookies = cookielib.LWPCookieJar( COOKIE_FILE)

def updateSessionCookie( ck):
    global session_cookie
    for c in ck:
        if c.name == "cinergy_s":
            session_cookie = c.value
            return True
    session_cookie = ''
    return False

def updateUserID( content):
    global user_id
    lines = content.split( '\n')
    for line in lines:
        if ".setId(" in line:
            match = re.search("\.setId\((\d+)\)", line)
            if match:
                user_id = match.group(1)
                log( "user id: " + user_id)
                return True
    user_id = ''
    return False

def ensure_login():
    global cookies
    opener = urllib2.build_opener( urllib2.HTTPCookieProcessor(cookies))
    urllib2.install_opener( opener)
    try:
        cookies.revert( ignore_discard=True)
    except IOError:
        pass

    reply = fetchHttp( TB_URL + "/login")
    cookies.save( ignore_discard=True)
    reply = fetchHttp( TB_URL + "/live")
    if updateSessionCookie( cookies) and updateUserID( reply):
        log( "login not required")
        return True

    log( "logging in...")
    url = TB_URL + "/login_check"
    args = { "login": settings.getSetting( id="login"),
             "password": settings.getSetting( id="password"),
             "keep_login": "1" }
    hdrs = { "Referer": 'https://www.teleboy.ch/login' }
    reply = fetchHttp( url, args, hdrs, post=True)
    reply = fetchHttp( TB_URL + "/live")

    if updateSessionCookie( cookies) and updateUserID( reply):
        cookies.save( ignore_discard=True)
        log( "login ok")
        return True

    log( "login failure")
    log( reply)
    notify( "Login Failure!", "Please set your login/password in the addon settings")
    os.unlink( xbmc.translatePath( COOKIE_FILE))
    return False

def fetchHttpWithCookies( url, args={}, hdrs={}, post=False):
    html = fetchHttp( url, args, hdrs, post)
    if "requires active login" in html:
        log( "invalid session")
        log ( html)
        notify( "Invalid session!", "Please restart the addon to force a new login/session")
        os.unlink( xbmc.translatePath( COOKIE_FILE))
        return False
    return html

def build_epg_line(itm, epg_format):
    show_title = None
    show_subtitle = None
    genre = None
    time_begin = None
    time_end = None

    if "title" in itm:
        show_title = itm["title"]

    if "subtitle" in itm:
        show_subtitle = itm["subtitle"]

    if "genre" in itm:
        genre_itm = itm["genre"]
        if genre_itm:
            if "name_en" in genre_itm:
                genre = genre_itm["name_en"]

    if "begin" in itm:
        time_begin = dateutil.parser.parse(itm["begin"])

    if "end" in itm:
        time_end = dateutil.parser.parse(itm["end"])
        time_now = datetime.datetime.now(dateutil.tz.tzlocal())
        time_left = time_end - time_now
        time_left_m = int(round((time_left.days*24*3600 + time_left.seconds + 0.0)/60))
    else:
        time_left_m = -1

    program_label = ": " + show_title  # Common program string
    if epg_format == '1':
        if time_left_m >= 0: program_label = "%s (noch %s')" % (program_label, time_left_m)
    if epg_format == '2':
        program_label = "%s (%s - %s)" % (program_label, time_begin.strftime('%H:%M'), time_end.strftime('%H:%M'))
    if epg_format == '3':
        if genre: program_label = "%s (%s)" % (program_label, genre)
    if epg_format == '4':
        if show_subtitle: program_label = "%s (%s)" % (program_label, show_subtitle)

    return program_label

def get_stationLogoURL( station):
    return IMG_URL + "/t_station/%d/icon320_dark.png" % int(station)

def get_json( url, args={}):
    if (session_cookie == ""):
        log( "no session cookie")
        notify( "Session cookie not found!", "Please set your login/password in the addon settings")
        return False

    hdrs = { "x-teleboy-apikey": API_KEY,
             "x-teleboy-session": session_cookie }
    ans = fetchHttpWithCookies( url, args, hdrs)
    if ans:
        return simplejson.loads( ans)
    else:
        return False

############
# TEMP
############
def addDirectoryItem( name, params={}, image="", folder=False):
    '''Add a list item to the XBMC UI.'''
    name = htmldecode( name)

    if folder:
      img = "DefaultFolder.png"
      li = xbmcgui.ListItem( name, iconImage=img)
    else:
      img = image if image else "DefaultVideo.png"
      li = xbmcgui.ListItem( name, iconImage=img, thumbnailImage=image)
      li.setProperty( "Video", "true")
      li.addContextMenuItems( [( 'Refresh', 'XBMC.Container.Update(%s)' % (plugin_refresh) )] )

    params_encoded = dict()
    for k in params.keys():
        params_encoded[k] = params[k].encode( "utf-8")
    url = plugin_url + '?' + urllib.urlencode( params_encoded)

    return xbmcplugin.addDirectoryItem( handle=plugin_handle, url=url, listitem=li, isFolder=folder, totalItems=0)
###########
# END TEMP
###########

def show_main_menu():
    addDirectoryItem( 'LiveTV - Favourites', { PARAMETER_KEY_MODE: MODE_FAV }, folder = True)
    addDirectoryItem( 'LiveTV - All channels', { PARAMETER_KEY_MODE: MODE_ALL }, folder = True)
    addDirectoryItem( 'Recordings - Ready', { PARAMETER_KEY_MODE: MODE_RECS }, folder = True)
    xbmcplugin.endOfDirectory( handle=plugin_handle, succeeded=True)
    return True

def show_channels( all_channels):
    epg_visible = settings.getSetting( id='epg_visible')
    epg_format = settings.getSetting( id='epg_format')

    if (all_channels):
        url = API_URL + "/epg/broadcasts/now"
    else:
        url = API_URL + "/users/%s/broadcasts/now" % (user_id)
    args = { "expand": "station,genre", "stream": "true" }
    broadcasts = get_json( url, args)

    if not broadcasts: return False
    items = broadcasts["data"]["items"]

    if not items: return False
    for itm in items:
        id = itm["station_id"]
        channel = itm["station"]["name"]

        if epg_visible == 'true':
            label = channel + build_epg_line( itm, epg_format)
        else: 
            label = channel

        img = get_stationLogoURL( id)
        addDirectoryItem( label, { PARAMETER_KEY_STATION: str(id), 
                                   PARAMETER_KEY_MODE: MODE_PLAY }, img)

        ll = "%s - %s" % (id, label)
        log( ll)

    xbmcplugin.endOfDirectory( handle=plugin_handle, succeeded=True)
    return True

def show_recordings():
    url = API_URL + "/users/%s/records/ready" % (user_id)
    args = { "limit": "500", "skip": "0" }
    recordings = get_json( url)

    if not recordings: return False
    items = recordings["data"]["items"]

    if not items: return False
    for itm in items:
        station_id = itm["station_id"]
        id = itm["id"]
        channel = itm["label"]
        show = itm["title"]
        rec_begin = dateutil.parser.parse(itm["begin"])
        rec_end = dateutil.parser.parse(itm["end"])
        duration = rec_end - rec_begin
        duration_m = int(round((duration.days*24*3600 + duration.seconds + 0.0)/60))
        genre = itm["genre"] if "genre" in itm else ""

        img = get_stationLogoURL( station_id)

        label = "%s: %s | %s (%s')" % (channel, show, genre, duration_m)

        addDirectoryItem( label, { PARAMETER_KEY_STATION: str(station_id), 
                                   PARAMETER_KEY_ASSETID: str(id), 
                                   PARAMETER_KEY_MODE: MODE_REPLAY }, img)

        ll = "%s - %s" % (id, label)
        log( ll)

    xbmcplugin.endOfDirectory( handle=plugin_handle, succeeded=True)
    return True

#
# xbmc entry point
############################################
#sayHi()

if not plugin_params:
    # new start
    show_main_menu()
    exit (1)

if not ensure_login():
    exit( 1)

params = dict(urlparse.parse_qsl(plugin_params))
mode = params.get(PARAMETER_KEY_MODE, "0")

# depending on the mode, call the appropriate function to build the UI or play video
if mode == MODE_FAV:
    if not show_channels(all_channels=False):
        xbmcplugin.endOfDirectory( handle=plugin_handle, succeeded=False)

elif mode == MODE_ALL:
    if not show_channels(all_channels=True):
        xbmcplugin.endOfDirectory( handle=plugin_handle, succeeded=False)

elif mode == MODE_RECS:
    if not show_recordings():
        notify( "No recordings found!", "You do not have any recording ready")
        xbmcplugin.endOfDirectory( handle=plugin_handle, succeeded=False)

elif mode == MODE_PLAY:
    station = params[PARAMETER_KEY_STATION]
    url = API_URL + "/users/%s/stream/live/%s" % (user_id, station)
    args = { "alternative": "false" }
    live_stream = get_json( url, args)
    if not live_stream:
        exit( 1)

    title = live_stream["data"]["epg"]["current"]["title"]
    url = live_stream["data"]["stream"]["url"]

    if not url: exit( 1)
    img = get_stationLogoURL( station)

    li = xbmcgui.ListItem( title, iconImage=img, thumbnailImage=img)
    li.setProperty( "IsPlayable", "true")
    li.setProperty( "Video", "true")

    xbmc.Player().play( url, li)

elif mode == MODE_REPLAY:
    station = params[PARAMETER_KEY_STATION]
    asset_id = params[PARAMETER_KEY_ASSETID]
    url = API_URL + "/users/%s/stream/record/%s" % (user_id, asset_id)
    live_stream = get_json( url)
    if not live_stream:
        exit( 1)

    title = live_stream["data"]["record"]["title"]
    url = live_stream["data"]["stream"]["url"]

    if not url: exit( 1)
    img = get_stationLogoURL( station)

    li = xbmcgui.ListItem( title, iconImage=img, thumbnailImage=img)
    li.setProperty( "IsPlayable", "true")
    li.setProperty( "Video", "true")

    xbmc.Player().play( url, li)

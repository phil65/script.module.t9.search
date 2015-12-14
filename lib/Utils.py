# -*- coding: utf8 -*-

# Copyright (C) 2015 - Philipp Temminghoff <phil65@kodi.tv>
# This program is Free Software see LICENSE file for details

import urllib
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import urllib2
import os
import time
import hashlib
import simplejson
import threading
import codecs
from functools import wraps

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_ICON = ADDON.getAddonInfo('icon')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_PATH = ADDON.getAddonInfo('path').decode("utf-8")
ADDON_VERSION = ADDON.getAddonInfo('version')
ADDON_DATA_PATH = xbmc.translatePath("special://profile/addon_data/%s" % ADDON_ID).decode("utf-8")
HOME = xbmcgui.Window(10000)
SETTING = ADDON.getSetting


def LANG(label_id):
    if 31000 <= label_id <= 33000:
        return ADDON.getLocalizedString(label_id)
    else:
        return xbmc.getLocalizedString(label_id)


def run_async(func):
    """
    Decorator to run a function in a separate thread
    """
    @wraps(func)
    def async_func(*args, **kwargs):
        func_hl = threading.Thread(target=func,
                                   args=args,
                                   kwargs=kwargs)
        func_hl.start()
        return func_hl

    return async_func


def busy_dialog(func):
    """
    Decorator to show busy dialog while function is running
    Only one of the decorated functions may run simultaniously
    """

    @wraps(func)
    def decorator(self, *args, **kwargs):
        xbmc.executebuiltin("ActivateWindow(busydialog)")
        result = func(self, *args, **kwargs)
        xbmc.executebuiltin("Dialog.Close(busydialog)")
        return result

    return decorator


def merge_dicts(*dict_args):
    '''
    Given any number of dicts, shallow copy and merge into a new dict,
    precedence goes to key value pairs in latter dicts.
    '''
    result = {}
    for dictionary in dict_args:
        result.update(dictionary)
    return result


def check_version():
    """
    check version, open TextViewer if update detected
    """
    if not SETTING("changelog_version") == ADDON_VERSION:
        xbmcgui.Dialog().textviewer(heading=LANG(24036),
                                    text=read_from_file(os.path.join(ADDON_PATH, "changelog.txt"), True))
        ADDON.setSetting("changelog_version", ADDON_VERSION)
    if not SETTING("first_start_infodialog"):
        ADDON.setSetting("first_start_infodialog", "True")
        xbmcgui.Dialog().ok(heading=ADDON_NAME,
                            line1=LANG(32140),
                            line2=LANG(32141))


def get_autocomplete_items(search_str):
    """
    get dict list with autocomplete labels from google
    """
    if SETTING("autocomplete_provider") == "youtube":
        return get_google_autocomplete_items(search_str, True)
    elif SETTING("autocomplete_provider") == "google":
        return get_google_autocomplete_items(search_str)
    else:
        return get_common_words_autocomplete_items(search_str)


def get_google_autocomplete_items(search_str, youtube=False):
    """
    get dict list with autocomplete labels from google
    """
    if not search_str:
        return []
    listitems = []
    headers = {'User-agent': 'Mozilla/5.0'}
    base_url = "http://clients1.google.com/complete/"
    url = "search?hl=%s&q=%s&json=t&client=serp" % (SETTING("autocomplete_lang"), urllib.quote_plus(search_str))
    if youtube:
        url += "&ds=yt"
    result = get_JSON_response(url=base_url + url,
                               headers=headers,
                               folder="Google")
    if not result or len(result) <= 1:
        return []
    for item in result[1]:
        if is_hebrew(item):
            search_str = item[::-1]
        else:
            search_str = item
        li = {"label": item,
              "path": "plugin://script.extendedinfo/?info=selectautocomplete&&id=%s" % search_str}
        listitems.append(li)
    return listitems


def is_hebrew(text):
    if type(text) != unicode:
        text = text.decode('utf-8')
    for chr in text:
        if ord(chr) >= 1488 and ord(chr) <= 1514:
            return True
    return False


def get_common_words_autocomplete_items(search_str):
    """
    get dict list with autocomplete labels from locally saved lists
    """
    listitems = []
    k = search_str.rfind(" ")
    if k >= 0:
        search_str = search_str[k + 1:]
    path = os.path.join(ADDON_PATH, "resources", "data", "common_%s.txt" % SETTING("autocomplete_lang_local"))
    with codecs.open(path, encoding="utf8") as f:
        for i, line in enumerate(f.readlines()):
            if not line.startswith(search_str) or len(line) <= 2:
                continue
            li = {"label": line,
                  "path": "plugin://script.extendedinfo/?info=selectautocomplete&&id=%s" % line}
            listitems.append(li)
            if len(listitems) > 10:
                break
    return listitems


def get_http(url=None, headers=False):
    """
    fetches data from *url, returns it as a string
    """
    succeed = 0
    if not headers:
        headers = {'User-agent': 'XBMC/14.0 ( phil65@kodi.tv )'}
    request = urllib2.Request(url)
    for (key, value) in headers.iteritems():
        request.add_header(key, value)
    while (succeed < 2) and (not xbmc.abortRequested):
        try:
            response = urllib2.urlopen(request, timeout=3)
            data = response.read()
            return data
        except:
            log("get_http: could not get data from %s" % url)
            xbmc.sleep(1000)
            succeed += 1
    return None


def get_JSON_response(url="", cache_days=7.0, folder=False, headers=False):
    """
    get JSON response for *url, makes use of prop and file cache.
    """
    now = time.time()
    hashed_url = hashlib.md5(url).hexdigest()
    if folder:
        cache_path = xbmc.translatePath(os.path.join(ADDON_DATA_PATH, folder))
    else:
        cache_path = xbmc.translatePath(os.path.join(ADDON_DATA_PATH))
    path = os.path.join(cache_path, hashed_url + ".txt")
    cache_seconds = int(cache_days * 86400.0)
    prop_time = HOME.getProperty(hashed_url + "_timestamp")
    if prop_time and now - float(prop_time) < cache_seconds:
        try:
            prop = simplejson.loads(HOME.getProperty(hashed_url))
            log("prop load for %s. time: %f" % (url, time.time() - now))
            if prop:
                return prop
        except:
            log("could not load prop data for %s" % url)
    if xbmcvfs.exists(path) and ((now - os.path.getmtime(path)) < cache_seconds):
        results = read_from_file(path)
        log("loaded file for %s. time: %f" % (url, time.time() - now))
    else:
        response = get_http(url, headers)
        try:
            results = simplejson.loads(response)
            log("download %s. time: %f" % (url, time.time() - now))
            save_to_file(results, hashed_url, cache_path)
        except:
            log("Exception: Could not get new JSON data from %s. Tryin to fallback to cache" % url)
            log(response)
            if xbmcvfs.exists(path):
                results = read_from_file(path)
            else:
                results = []
    if results:
        HOME.setProperty(hashed_url + "_timestamp", str(now))
        HOME.setProperty(hashed_url, simplejson.dumps(results))
        return results
    else:
        return []


def log(txt):
    if isinstance(txt, str):
        txt = txt.decode("utf-8", 'ignore')
    message = u'%s: %s' % (ADDON_ID, txt)
    xbmc.log(msg=message.encode("utf-8", 'ignore'),
             level=xbmc.LOGDEBUG)


def get_browse_dialog(default="", heading=LANG(1024), dlg_type=3, shares="files", mask="", use_thumbs=False, treat_as_folder=False):
    dialog = xbmcgui.Dialog()
    value = dialog.browse(dlg_type, heading, shares, mask, use_thumbs, treat_as_folder, default)
    return value


def save_to_file(content, filename, path=""):
    """
    dump json and save to *filename in *path
    """
    if path == "":
        text_file_path = get_browse_dialog() + filename + ".txt"
    else:
        if not xbmcvfs.exists(path):
            xbmcvfs.mkdirs(path)
        text_file_path = os.path.join(path, filename + ".txt")
    now = time.time()
    text_file = xbmcvfs.File(text_file_path, "w")
    simplejson.dump(content, text_file)
    text_file.close()
    log("saved textfile %s. Time: %f" % (text_file_path, time.time() - now))
    return True


def read_from_file(path="", raw=False):
    """
    return data from file with *path
    """
    if path == "":
        path = get_browse_dialog(dlg_type=1)
    if not xbmcvfs.exists(path):
        return False
    try:
        with open(path) as f:
            log("opened textfile %s." % (path))
            if not raw:
                result = simplejson.load(f)
            else:
                result = f.read()
        return result
    except:
        log("failed to load textfile: " + path)
        return False


def notify(header="", message="", icon=ADDON_ICON, time=5000, sound=True):
    xbmcgui.Dialog().notification(heading=header,
                                  message=message,
                                  icon=icon,
                                  time=time,
                                  sound=sound)


def get_kodi_json(method, params):
    json_query = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "%s", "params": %s, "id": 1}' % (method, params))
    json_query = unicode(json_query, 'utf-8', errors='ignore')
    return simplejson.loads(json_query)


def pass_dict_to_skin(data=None, prefix="", debug=False, precache=False, window_id=10000):
    window = xbmcgui.Window(window_id)
    if not data:
        return None
    threads = []
    image_requests = []
    for (key, value) in data.iteritems():
        if not value:
            continue
        value = unicode(value)
        if precache:
            if value.startswith("http") and (value.endswith(".jpg") or value.endswith(".png")):
                if value not in image_requests and value:
                    thread = GetFileThread(value)
                    threads += [thread]
                    thread.start()
                    image_requests.append(value)
        window.setProperty('%s%s' % (prefix, str(key)), value)
        if debug:
            log('%s%s' % (prefix, str(key)) + value)
    for x in threads:
        x.join()

def set_window_props(name, data, prefix="", debug=False):
    if not data:
        HOME.setProperty('%s%s.Count' % (prefix, name), '0')
        log("%s%s.Count = None" % (prefix, name))
        return None
    for (count, result) in enumerate(data):
        if debug:
            log("%s%s.%i = %s" % (prefix, name, count + 1, str(result)))
        for (key, value) in result.iteritems():
            value = unicode(value)
            HOME.setProperty('%s%s.%i.%s' % (prefix, name, count + 1, str(key)), value)
            if key.lower() in ["poster", "banner", "fanart", "clearart", "clearlogo", "landscape",
                               "discart", "characterart", "tvshow.fanart", "tvshow.poster",
                               "tvshow.banner", "tvshow.clearart", "tvshow.characterart"]:
                HOME.setProperty('%s%s.%i.Art(%s)' % (prefix, name, count + 1, str(key)), value)
            if debug:
                log('%s%s.%i.%s --> ' % (prefix, name, count + 1, str(key)) + value)
    HOME.setProperty('%s%s.Count' % (prefix, name), str(len(data)))


def create_listitems(data=None, preload_images=0):
    INT_INFOLABELS = ["year", "episode", "season", "top250", "tracknumber", "playcount", "overlay"]
    FLOAT_INFOLABELS = ["rating"]
    STRING_INFOLABELS = ["genre", "director", "mpaa", "plot", "plotoutline", "title", "originaltitle",
                         "sorttitle", "duration", "studio", "tagline", "writer", "tvshowtitle", "premiered",
                         "status", "code", "aired", "credits", "lastplayed", "album", "votes", "trailer", "dateadded"]
    if not data:
        return []
    itemlist = []
    threads = []
    image_requests = []
    for (count, result) in enumerate(data):
        listitem = xbmcgui.ListItem('%s' % (str(count)))
        for (key, value) in result.iteritems():
            if not value:
                continue
            value = unicode(value)
            if count < preload_images:
                if value.startswith("http://") and (value.endswith(".jpg") or value.endswith(".png")):
                    if value not in image_requests:
                        thread = GetFileThread(value)
                        threads += [thread]
                        thread.start()
                        image_requests.append(value)
            if key.lower() in ["name", "label"]:
                listitem.setLabel(value)
            elif key.lower() in ["label2"]:
                listitem.setLabel2(value)
            elif key.lower() in ["title"]:
                listitem.setLabel(value)
                listitem.setInfo('video', {key.lower(): value})
            elif key.lower() in ["thumb"]:
                listitem.setThumbnailImage(value)
                listitem.setArt({key.lower(): value})
            elif key.lower() in ["icon"]:
                listitem.setIconImage(value)
                listitem.setArt({key.lower(): value})
            elif key.lower() in ["path"]:
                listitem.setPath(path=value)
                # listitem.setProperty('%s' % (key), value)
            # elif key.lower() in ["season", "episode"]:
            #     listitem.setInfo('video', {key.lower(): int(value)})
            #     listitem.setProperty('%s' % (key), value)
            elif key.lower() in ["poster", "banner", "fanart", "clearart", "clearlogo", "landscape",
                                 "discart", "characterart", "tvshow.fanart", "tvshow.poster",
                                 "tvshow.banner", "tvshow.clearart", "tvshow.characterart"]:
                listitem.setArt({key.lower(): value})
            elif key.lower() in INT_INFOLABELS:
                try:
                    listitem.setInfo('video', {key.lower(): int(value)})
                except:
                    pass
            elif key.lower() in STRING_INFOLABELS:
                listitem.setInfo('video', {key.lower(): value})
            elif key.lower() in FLOAT_INFOLABELS:
                try:
                    listitem.setInfo('video', {key.lower(): "%1.1f" % float(value)})
                except:
                    pass
            # else:
            listitem.setProperty('%s' % (key), value)
        listitem.setProperty("index", str(count))
        itemlist.append(listitem)
    for x in threads:
        x.join()
    return itemlist

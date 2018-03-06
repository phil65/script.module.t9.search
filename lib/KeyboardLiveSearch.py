# -*- coding: utf8 -*-

# Copyright (C) 2015 - Philipp Temminghoff <phil65@kodi.tv>
# This program is Free Software see LICENSE file for details

import time
from threading import Timer
import xbmcgui
import T9Utils
import os
from collections import deque
import ast
from kodi65 import ActionHandler
import AutoCompletion

ch = ActionHandler()


class KeyboardLiveSearch(object):

    def __init__(self, call=None, start_value="", history="Default"):
        daemon = Daemon(u'script-script.module.t9.search-Main.xml',
                        os.path.join(os.path.dirname(__file__), ".."),
                        call=call,
                        start_value=start_value,
                        history=history)
        self.search_str = daemon.search_str


class Daemon(xbmcgui.WindowXMLDialog):

    def __init__(self, *args, **kwargs):
        self.callback = kwargs.get("call")
        self.search_str = kwargs.get("start_value", "")
        self.previous = False
        self.prev_time = 0
        self.timer = None
        self.color_timer = None
        self.setting_name = kwargs.get("history")
        setting_string = T9Utils.SETTING(self.setting_name)
        if self.setting_name and setting_string:
            self.last_searches = deque(ast.literal_eval(setting_string), maxlen=10)
        else:
            self.last_searches = deque(maxlen=10)

    def onInit(self):
        self.get_autocomplete_labels_async()
        self.update_search_label_async()
        self.getControl(600).setLabel("[B]%s[/B]_" % self.search_str)

    def onClick(self, control_id):
        ch.serve(control_id, self)

    def onAction(self, action):
        ch.serve_action(action, self.getFocusId(), self)

    @ch.click(9090)
    def panel_click(self):
        self.set_t9_letter(letters=self.listitem.getProperty("value"),
                           number=self.listitem.getProperty("key"),
                           button=int(self.listitem.getProperty("index")))

    @ch.click(9091)
    def set_autocomplete(self):
        self.search_str = self.listitem.getLabel()
        self.getControl(600).setLabel("[B]%s[/B]_" % self.search_str)
        self.get_autocomplete_labels_async()
        if self.timer:
            self.timer.cancel()
        self.timer = Timer(0.0, self.search, (self.search_str,))
        self.timer.start()

    @T9Utils.run_async
    def update_search_label_async(self):
        while True:
            time.sleep(1)
            if int(time.time()) % 2 == 0:
                self.getControl(600).setLabel("[B]%s[/B]_" % self.search_str)
            else:
                self.getControl(600).setLabel("[B]%s[/B][COLOR 00FFFFFF]_[/COLOR]" % self.search_str)

    @T9Utils.run_async
    def get_autocomplete_labels_async(self):
        self.getControl(9091).reset()
        if self.search_str:
            listitems = AutoCompletion.get_autocomplete_items(self.search_str)
        else:
            listitems = list(self.last_searches)
        self.getControl(9091).addItems(T9Utils.create_listitems(listitems))

    def save_autocomplete(self):
        if not self.search_str:
            return None
        listitem = {"label": self.search_str}
        if listitem in self.last_searches:
            self.last_searches.remove(listitem)
        self.last_searches.appendleft(listitem)
        T9Utils.ADDON.setSetting(self.setting_name, str(list(self.last_searches)))

    def set_t9_letter(self, letters, number, button):
        now = time.time()
        time_diff = now - self.prev_time
        self.search_str = ""
        if time_diff < 1:
            if self.color_timer:
                self.color_timer.cancel()
            self.prev_time = now
            idx = (letters.index(self.search_str[-1]) + 1) % len(letters)
            self.search_str = self.search_str[:-1] + letters[idx]
            self.color_labels(idx, letters, button)
        if self.timer:
            self.timer.cancel()
        self.timer = Timer(1.0, self.search, (self.search_str,))
        self.timer.start()
        self.getControl(600).setLabel("[B]%s[/B]_" % self.search_str)
        self.get_autocomplete_labels_async()

    def use_classic_search(self):
        self.close()
        result = xbmcgui.Dialog().input(heading=T9Utils.LANG(16017),
                                        type=xbmcgui.INPUT_ALPHANUM)
        if result and result > -1:
            self.search_str = result
            self.callback(result)
            self.save_autocomplete()

    def search(self, search_str):
        self.callback(search_str)

    def color_labels(self, index, letters, button):
        letter = letters[index]
        label = "[COLOR=FFFF3333]%s[/COLOR]" % letter
        self.getControl(9090).getListItem(button).setLabel2(letters.replace(letter, label))
        self.color_timer = Timer(1.0, self.reset_color, (self.getControl(9090).getListItem(button),))
        self.color_timer.start()

    def reset_color(self, item):
        label = item.getLabel2()
        label = label.replace("[COLOR=FFFF3333]", "").replace("[/COLOR]", "")
        item.setLabel2(label)

from __future__ import absolute_import
from Screens.Screen import Screen

# for localized messages
from . import _

from Components.Label import Label
from Components.Button import Button
from Components.Pixmap import Pixmap
from Components.ActionMap import ActionMap

from .skin_templates import skin_about

import os
import sys


class AutoBouquetsMaker_About(Screen):
	skin = skin_about()

	def __init__(self, session):
		self.session = session
		Screen.__init__(self, session)
		Screen.setTitle(self, _("AutoBouquetsMaker") + " - " + _("About"))

		self["about"] = Label("")
		self["oealogo"] = Pixmap()

		self["actions"] = ActionMap(["SetupActions", "ColorActions", "MenuActions"],
		{
			"red": self.quit,
			"cancel": self.quit,
			"menu": self.quit,
		}, -2)

		self["key_red"] = Button(_("Close"))

		from .version import PLUGIN_VERSION

		credit = "OE-Alliance AutoBouquetsMaker %s (c) 2012 \nSandro Cavazzoni & Andrew Blackburn\n" % PLUGIN_VERSION
		credit += "http://github.com/oe-alliance\n"
		credit += "http://www.sifteam.eu\n"
		credit += "http://www.world-of-satellite.com\n\n"
		credit += "Application credits:\n"
		credit += "- Sandro Cavazzoni aka skaman (main developer)\n"
		credit += "- Andrew Blackburn aka AndyBlac (main developer)\n"
		credit += "- Peter de Jonge aka PeterJ (developer)\n"
		credit += "- Huevos (developer)\n\n"
		credit += "Sources credits:\n"
		credit += "- LraiZer (used his AutoBouquets script as a start point)"
		self["about"].setText(credit)
		self.onFirstExecBegin.append(self.setImages)

	def setImages(self):
		self["oealogo"].instance.setPixmapFromFile("%s/images/oea-logo.png" % (os.path.dirname(sys.modules[__name__].__file__)))

	def quit(self):
		self.close()

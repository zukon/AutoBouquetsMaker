# The purpose of this file is to avoid unnecessary skin and code duplication.
# Used by hidesections.py and keepbouquets.py as the parent class.

from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.config import configfile
from Components.Sources.List import List

from Screens.MessageBox import MessageBox

from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN, SCOPE_SKIN

try:
	from skin import findSkinScreen
except ImportError as e:
	print "[ABM-listBuilder] ImportError:", e

class AutoBouquetsMaker_listBuilder():
	skin = """
		<screen position="center,center" size="600,500">
			<widget source="key_red" render="Label" position="0,0" size="140,40" valign="center" halign="center" font="Regular;18" backgroundColor="red" foregroundColor="white"/>
			<widget source="key_green" render="Label" position="150,0" size="140,40" valign="center" halign="center" font="Regular;18" backgroundColor="green" foregroundColor="white"/>
			<widget source="list" render="Listbox" position="10,50" size="580,450" scrollbarMode="showOnDemand">
				<convert type="TemplatedMultiContent">
					{"template": [
						MultiContentEntryPixmapAlphaTest(pos = (10, 0), size = (25, 24), png = 0),
						MultiContentEntryText(pos = (47, 0), size = (300, 30), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_TOP, text = 1),
						MultiContentEntryText(pos = (350, 0), size = (210, 30), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_TOP, text = 2),
						],
						"fonts": [gFont("Regular", 22)],
						"itemHeight": 30
					}
				</convert>
			</widget>
		</screen>"""

	def __init__(self):
		self.scope = SCOPE_CURRENT_SKIN
		self.path = ""
		try:
			if findSkinScreen(self.__class__.__name__) is None: # plugin is not skinned in active skin
				self.scope = SCOPE_SKIN
				self.path = "skin_default/"
		except NameError as e: # for distros without findSkinScreen() method
			print "[ABM-listBuilder] NameError:", e

		self.drawList = []
		self["list"] = List(self.drawList)
		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("Save"))
		self["actions"] = ActionMap(["OkCancelActions", "ColorActions"],
				{
					"red": self.keyCancel,
					"green": self.keySave,
					"ok": self.ok,
					"cancel": self.keyCancel,
				}, -2)

	def buildListEntry(self, enabled, name, type):
		pixmap = LoadPixmap(cached=True, path=resolveFilename(self.scope, "%sicons/lock_%s.png" % (self.path, "on" if enabled else "off")))
		return((pixmap, str(name), str(type)))
	
	def keySave(self):
		self.configItem.save()
		configfile.save()
		self.close()

	def cancelConfirm(self, result):
		if not result:
			return
		self.configItem.cancel()
		self.close()

	def keyCancel(self):
		if self.startlist != self.configItem.getValue():
			self.session.openWithCallback(self.cancelConfirm, MessageBox, _("Really close without saving settings?"))
		else:
			self.close()

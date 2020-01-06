# -*- coding: utf-8 -*-
# for localized messages
from . import _

from Screens.Screen import Screen
from Components.config import config
from listbuilder import AutoBouquetsMaker_listBuilder
from scanner.manager import Manager

class AutoBouquetsMaker_KeepBouquets(Screen, AutoBouquetsMaker_listBuilder):
	# embedded skin is in listbuilder.py

	ABM_BOUQUET_PREFIX = "userbouquet.abm."

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		Screen.setTitle(self, _("AutoBouquetsMaker Keep bouquets"))
		self.configItem = config.autobouquetsmaker.keepbouquets
		self.startlist = self.configItem.getValue()
		AutoBouquetsMaker_listBuilder.__init__(self)

		self.refresh()

	def refresh(self):
		bouquets = Manager().getBouquetsList()
		self.listTv = bouquets["tv"]
		self.listRadio = bouquets["radio"]
		self.drawList = []
		self.listAll = []
		self.bouquets = self.configItem.value.split("|")

		if self.listTv is not None and self.listRadio is not None:
			for bouquet in self.listTv:
				if bouquet["filename"][:len(self.ABM_BOUQUET_PREFIX)] == self.ABM_BOUQUET_PREFIX:
					continue
				if bouquet["filename"] in self.bouquets:
					self.drawList.append(self.buildListEntry(True, bouquet["name"], "TV"))
				else:
					self.drawList.append(self.buildListEntry(False, bouquet["name"], "TV"))
				self.listAll.append(bouquet["filename"])

			for bouquet in self.listRadio:
				if bouquet["filename"][:len(self.ABM_BOUQUET_PREFIX)] == self.ABM_BOUQUET_PREFIX:
					continue
				if bouquet["filename"] in self.bouquets:
					self.drawList.append(self.buildListEntry(True, bouquet["name"], "Radio"))
				else:
					self.drawList.append(self.buildListEntry(False, bouquet["name"], "Radio"))
				self.listAll.append(bouquet["filename"])
		self["list"].setList(self.drawList)

	def ok(self):
		if len(self.listAll) == 0:
			return
		index = self["list"].getIndex()
		if self.listAll[index] in self.bouquets:
			self.bouquets.remove(self.listAll[index])
		else:
			self.bouquets.append(self.listAll[index])
		self.configItem.value = "|".join(self.bouquets)
		self.refresh()
		self["list"].setIndex(index)

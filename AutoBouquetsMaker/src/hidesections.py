# -*- coding: utf-8 -*-
# for localized messages
from . import _

from Screens.Screen import Screen
from Components.config import config
from listbuilder import AutoBouquetsMaker_listBuilder
from scanner.manager import Manager
from scanner.providerconfig import ProviderConfig

class AutoBouquetsMaker_HideSections(Screen, AutoBouquetsMaker_listBuilder):
	# embedded skin is in listbuilder.py

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		Screen.setTitle(self, _("AutoBouquetsMaker Hide sections"))
		self.configItem = config.autobouquetsmaker.hidesections
		self.startlist = self.configItem.getValue()
		AutoBouquetsMaker_listBuilder.__init__(self)

		self.providers = Manager().getProviders()
		self.providers_enabled = []
		providers_tmp = config.autobouquetsmaker.providers.value.split("|")
		for provider_tmp in providers_tmp:
			provider_config = ProviderConfig(provider_tmp)

			if not provider_config.isValid():
				continue

			if provider_config.getProvider() not in self.providers:
				continue

			self.providers_enabled.append(provider_config.getProvider())

		self.housekeeping()
		self.refresh()

	def refresh(self):
		self.providers_selected = self.configItem.value.split("|")
		self.drawList = []
		self.listAll = []

		for provider in self.providers_enabled:
			for section in sorted(self.providers[provider]["sections"].keys()):
				key = provider + ":" + str(section)
				self.listAll.append(key)
				self.drawList.append(self.buildListEntry(key in self.providers_selected, self.providers[provider]["sections"][section], self.providers[provider]["name"]))

		self["list"].setList(self.drawList)

	def ok(self):
		if len(self.listAll) == 0:
			return
		index = self["list"].getIndex()
		if self.listAll[index] in self.providers_selected:
			self.providers_selected.remove(self.listAll[index])
		else:
			self.providers_selected.append(self.listAll[index])
		self.configItem.value = "|".join(self.providers_selected)
		self.refresh()
		self["list"].setIndex(index)

	def housekeeping(self):
		# remove non-existent hidden sections, due to changes in the provider file
		hidden_sections = self.configItem.value.split("|")
		new_hidden_sections = []
		for provider in self.providers_enabled:
			for section in sorted(self.providers[provider]["sections"].keys()):
				key = provider + ":" + str(section)
				if key in hidden_sections:
					new_hidden_sections.append(key)
		self.configItem.value = "|".join(new_hidden_sections)

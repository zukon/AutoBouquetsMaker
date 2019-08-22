# for localized messages
from .. import _

from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.ProgressBar import ProgressBar
from Components.Sources.Progress import Progress
from Components.Sources.FrontendStatus import FrontendStatus

from Components.config import config, configfile
from Components.NimManager import nimmanager
from enigma import eTimer, eDVBDB, eDVBFrontendParametersSatellite,eDVBFrontendParametersTerrestrial, eDVBFrontendParametersCable, eDVBResourceManager, eDVBFrontendParameters

from manager import Manager
from providerconfig import ProviderConfig
from providers import Providers
from time import localtime, time, strftime, mktime

from .. import log
import os
import sys

from Tools.Directories import resolveFilename, fileExists
try:
	from Tools.Directories import SCOPE_ACTIVE_SKIN
except:
	pass

class AutoBouquetsMaker(Screen):
	skin = """
	<screen position="c-300,e-80" size="600,70" flags="wfNoBorder" >
		<widget name="background" position="0,0" size="600,70" zPosition="-1" />
		<widget name="action" halign="center" valign="center" position="65,10" size="520,20" font="Regular;18" backgroundColor="#11404040" transparent="1" />
		<widget name="status" halign="center" valign="center" position="65,35" size="520,20" font="Regular;18" backgroundColor="#11000000" transparent="1" />
		<widget name="progress" position="65,55" size="520,5" borderWidth="1" backgroundColor="#11000000"/>
	</screen>"""

	LOCK_TIMEOUT_FIXED = 100 	# 100ms for tick - 10 sec
	LOCK_TIMEOUT_ROTOR = 1200 	# 100ms for tick - 120 sec
	ABM_BOUQUET_PREFIX = "userbouquet.abm."

	def __init__(self, session, args = 0):
		self.printconfig()
		self.session = session
		Screen.__init__(self, session)
		Screen.setTitle(self, _("AutoBouquetsMaker"))

		self.frontend = None
		self.rawchannel = None
		self.postScanService = None
		self.providers = Manager().getProviders()

		self["background"] = Pixmap()
		self["action"] = Label(_("Starting scanner"))
		self["status"] = Label("")
		self["progress"] = ProgressBar()
		self["progress_text"] = Progress()
		self["tuner_text"] = Label("")
		self["Frontend"] = FrontendStatus(frontend_source = lambda : self.frontend, update_interval = 100)

		# dependent providers
		self.dependents = {}
		for provider_key in self.providers:
			if len(self.providers[provider_key]["dependent"]) > 0 and self.providers[provider_key]["dependent"] in self.providers:
				if self.providers[provider_key]["dependent"] not in self.dependents:
					self.dependents[self.providers[provider_key]["dependent"]] = []
				self.dependents[self.providers[provider_key]["dependent"]].append(provider_key)

		# get ABM config string including dependents
		self.abm_settings_str = self.getABMsettings()

		self.actionsList = []

		self.onFirstExecBegin.append(self.firstExec)

	def firstExec(self, postScanService=None):
		from Screens.Standby import inStandby
		if not inStandby:
			try:
				png = resolveFilename(SCOPE_ACTIVE_SKIN, "autobouquetsmaker/background.png")
			except:
				png = None
			if not png or not fileExists(png):
				png = "%s/../images/background.png" % os.path.dirname(sys.modules[__name__].__file__)
			self["background"].instance.setPixmapFromFile(png)

		if len(self.abm_settings_str) > 0:
			if not inStandby:
				self["action"].setText(_('Loading bouquets...'))
				self["status"].setText(_("Services: 0 video - 0 radio"))
			self.timer = eTimer()
			self.timer.callback.append(self.go)
			self.timer.start(100, 1)
		else:
			self.showError(_('Please first setup, in configuration'))

	def showError(self, message):
		from Screens.Standby import inStandby
		self.releaseFrontend()
		self.restartService()
		if not inStandby:
			question = self.session.open(MessageBox, message, MessageBox.TYPE_ERROR)
			question.setTitle(_("AutoBouquetsMaker"))
		self.close()

	def keyCancel(self):
		self.releaseFrontend()
		self.restartService()
		self.close()

	def go(self):
		from Screens.Standby import inStandby
		self.manager = Manager()
		self.manager.setPath("/etc/enigma2")
		self.manager.setAddPrefix(config.autobouquetsmaker.addprefix.value)

		self.selectedProviders = {}
		self.actionsList = []

		providers_tmp = self.abm_settings_str.split("|")

		for provider_tmp in providers_tmp:
			provider_config = ProviderConfig(provider_tmp)
			if provider_config.isValid() and Providers().providerFileExists(provider_config.getProvider()):
				self.actionsList.append(provider_config.getProvider())
				self.selectedProviders[provider_config.getProvider()] = provider_config

		if config.autobouquetsmaker.keepallbouquets.getValue():
			bouquets = Manager().getBouquetsList()
			bouquets_tv = []
			bouquets_radio = []
			for bouquet in bouquets["tv"]:
				if bouquet["filename"][:len(self.ABM_BOUQUET_PREFIX)] == self.ABM_BOUQUET_PREFIX:
					continue
				if len(bouquet["filename"]) > 0:
					bouquets_tv.append(bouquet["filename"])
			for bouquet in bouquets["radio"]:
				if bouquet["filename"][:len(self.ABM_BOUQUET_PREFIX)] == self.ABM_BOUQUET_PREFIX:
					continue
				if len(bouquet["filename"]) > 0:
					bouquets_radio.append(bouquet["filename"])
			self.manager.setBouquetsToKeep(bouquets_tv, bouquets_radio)
		else:
			bouquets = config.autobouquetsmaker.keepbouquets.value.split("|")
			bouquets_tv = []
			bouquets_radio = []
			for bouquet in bouquets:
				if bouquet.endswith(".tv"):
					bouquets_tv.append(bouquet)
				elif bouquet.endswith(".radio"):
					bouquets_radio.append(bouquet)
			self.manager.setBouquetsToKeep(bouquets_tv, bouquets_radio)

		bouquetsToHide = {}
		bouquets = config.autobouquetsmaker.hidesections.value.split("|")
		for bouquet in bouquets:
			tmp = bouquet.split(":")
			if len(tmp) != 2:
				continue

			if tmp[0].strip() not in bouquetsToHide:
				bouquetsToHide[tmp[0].strip()] = []

			bouquetsToHide[tmp[0].strip()].append(int(tmp[1].strip()))
		self.manager.setBouquetsToHide(bouquetsToHide)

		self.manager.load()

		self.progresscount = (len(self.actionsList) * 2) + 3
		self.progresscurrent = 1

		if not inStandby:
			self["progress_text"].range = self.progresscount
			self["progress_text"].value = self.progresscurrent
			self["progress"].setRange((0, self.progresscount))
			self["progress"].setValue(self.progresscurrent)

		self.timer = eTimer()
		self.timer.callback.append(self.doActions)
		self.timer.start(100, 1)

	def doActions(self):
		from Screens.Standby import inStandby
		if len(self.actionsList) == 0:
			self.progresscurrent += 1
			if not inStandby:
				self["progress_text"].value = self.progresscurrent
				self["progress"].setValue(self.progresscurrent)
				self["action"].setText(_('Bouquets generation...'))
				self["status"].setText(_("Services: %d video - %d radio") % (self.manager.getServiceVideoRead(), self.manager.getServiceAudioRead()))
				self["tuner_text"].setText("")
			self.timer = eTimer()
			self.timer.callback.append(self.doBuildIndex)
			self.timer.start(100, 1)
			return

		self.currentAction = self.actionsList[0]
		del(self.actionsList[0])

		self.progresscurrent += 1
		if not inStandby:
			self["progress_text"].value = self.progresscurrent
			self["progress"].setValue(self.progresscurrent)
			self["action"].setText(_("Tuning %s...") % str(self.providers[self.currentAction]["name"]))
			self["status"].setText(_("Services: %d video - %d radio") % (self.manager.getServiceVideoRead(), self.manager.getServiceAudioRead()))
			self["tuner_text"].setText("")
		self.timer = eTimer()
		self.timer.callback.append(self.doTune)
		self.timer.start(100, 1)

	def doTune(self):
		print>>log, "[ABM-main][doTune] searching for tuner for %s" % self.providers[self.currentAction]["name"]
		from Screens.Standby import inStandby
		if self.providers[self.currentAction]["streamtype"] == "dvbs":
			transponder = self.providers[self.currentAction]["transponder"]
		else:
			bouquet_key = None
			providers_tmp = self.abm_settings_str.split("|")
			for provider_tmp in providers_tmp:
				provider_config = ProviderConfig(provider_tmp)
				provider_key = provider_config.getProvider()
				if self.currentAction != provider_key:
					continue
				bouquet_key = provider_config.getArea()

			if not bouquet_key:
				print>>log, "[ABM-main][doTune] No area found"
				self.showError(_('No area found'))
				return

			transponder = self.providers[self.currentAction]["bouquets"][bouquet_key]

		nimList = []
		for nim in nimmanager.nim_slots:
			if self.providers[self.currentAction]["streamtype"] == "dvbs" and nim.isCompatible("DVB-S"):
				try:
					if nim.isFBCTuner() and not nim.isFBCRoot():
						continue # do not load FBC links, only root tuners
				except:
					pass
			try: # OpenPLi Hot Switch compatible image
				if (nim.config_mode not in ("loopthrough", "satposdepends", "nothing")) and \
					{"dvbs": "DVB-S", "dvbc": "DVB-C", "dvbt": "DVB-T"}.get(self.providers[self.currentAction]["streamtype"], "UNKNOWN") in [x[:5] for x in nim.getTunerTypesEnabled()]:
					nimList.append(nim.slot)
			except AttributeError:
				try:
					if (nim.config_mode not in ("loopthrough", "satposdepends", "nothing")) and \
						((self.providers[self.currentAction]["streamtype"] == "dvbs" and nim.isCompatible("DVB-S")) or \
						(self.providers[self.currentAction]["streamtype"] == "dvbc" and (nim.isCompatible("DVB-C") or (nim.isCompatible("DVB-S") and nim.canBeCompatible("DVB-C")))) or \
						(self.providers[self.currentAction]["streamtype"] == "dvbt" and (nim.isCompatible("DVB-T") or (nim.isCompatible("DVB-S") and nim.canBeCompatible("DVB-T"))))):
						nimList.append(nim.slot)
				except AttributeError: # OpenATV > 5.3
					if (self.providers[self.currentAction]["streamtype"] == "dvbs" and nim.canBeCompatible("DVB-S") and nim.config_mode_dvbs not in ("loopthrough", "satposdepends", "nothing")) or \
						(self.providers[self.currentAction]["streamtype"] == "dvbc" and nim.canBeCompatible("DVB-C") and nim.config_mode_dvbc != "nothing") or \
						(self.providers[self.currentAction]["streamtype"] == "dvbt" and nim.canBeCompatible("DVB-T") and nim.config_mode_dvbt != "nothing"):
						nimList.append(nim.slot)

		if len(nimList) == 0:
			print>>log, "[ABM-main][doTune] No NIMs found"
			self.showError(_('No NIMs found for ') + self.providers[self.currentAction]["name"])
			return

		resmanager = eDVBResourceManager.getInstance()
		if not resmanager:
			print>>log, "[ABM-main][doTune] Cannot retrieve Resource Manager instance"
			self.showError(_('Cannot retrieve Resource Manager instance'))
			return

		if self.providers[self.currentAction]["streamtype"] == "dvbs":
			print>>log, "[ABM-main][doTune] Search NIM for orbital position %d" % transponder["orbital_position"]
		else:
			print>>log, "[ABM-main][doTune] Search NIM"

		# stop pip if running
		if self.session.pipshown:
			self.session.pipshown = False
			del self.session.pip
			print>>log, "[ABM-main][doTune] Stopping PIP."

		# stop currently playing service if it is using a tuner in ("loopthrough", "satposdepends")
		currentlyPlayingNIM = None
		currentService = self.session and self.session.nav.getCurrentService()
		frontendInfo = currentService and currentService.frontendInfo()
		frontendData = frontendInfo and frontendInfo.getAll(True)
		if frontendData is not None:
			currentlyPlayingNIM = frontendData.get("tuner_number", None)
			if self.providers[self.currentAction]["streamtype"] == "dvbs" and currentlyPlayingNIM is not None and nimmanager.nim_slots[currentlyPlayingNIM].isCompatible("DVB-S"):
				try:
					nimConfigMode = nimmanager.nim_slots[currentlyPlayingNIM].config_mode
				except AttributeError: # OpenATV > 5.3
					nimConfigMode = nimmanager.nim_slots[currentlyPlayingNIM].config_mode_dvbs
				if nimConfigMode in ("loopthrough", "satposdepends"):
					self.postScanService = self.session.nav.getCurrentlyPlayingServiceReference()
					self.session.nav.stopService()
					currentlyPlayingNIM = None
					print>>log, "[ABM-main][doTune] The active service was using a %s tuner, so had to be stopped (slot id %s)." % (nimConfigMode, currentlyPlayingNIM)
		del frontendInfo
		del currentService

		current_slotid = -1
		self.releaseFrontend()

		nimList.reverse() # start from the last
		for slotid in nimList:
			if self.providers[self.currentAction]["streamtype"] == "dvbs":
				sats = nimmanager.getSatListForNim(slotid)
				for sat in sats:
					if sat[0] == transponder["orbital_position"]:
						if current_slotid == -1:	# mark the first valid slotid in case of no other one is free
							current_slotid = slotid

						self.rawchannel = resmanager.allocateRawChannel(slotid)
						if self.rawchannel:
							print>>log, "[ABM-main][doTune] Nim found on slot id %d with sat %s" % (slotid, sat[1])
							current_slotid = slotid
						break
			else:
				if current_slotid == -1:	# mark the first valid slotid in case of no other one is free
					current_slotid = slotid
				self.rawchannel = resmanager.allocateRawChannel(slotid)
				if self.rawchannel:
 					print>>log, "[ABM-main][doTune] Nim found on slot id %d" % (slotid)
					current_slotid = slotid
					break

			if self.rawchannel:
				break

		if current_slotid == -1:
			print>>log, "[ABM-main][doTune] No valid NIM found"
			self.showError(_('No valid NIM found for ') + self.providers[self.currentAction]["name"])
			return

		if not self.rawchannel:
			# if we are here the only possible option is to close the active service
			if currentlyPlayingNIM in nimList:
				slotid = currentlyPlayingNIM
				if self.providers[self.currentAction]["streamtype"] == "dvbs":
					sats = nimmanager.getSatListForNim(slotid)
					for sat in sats:
						if sat[0] == transponder["orbital_position"]:
							print>>log, "[ABM-main][doTune] Nim found on slot id %d but it's busy. Stopping active service" % slotid
							self.postScanService = self.session.nav.getCurrentlyPlayingServiceReference()
							self.session.nav.stopService()
							self.rawchannel = resmanager.allocateRawChannel(slotid)
							if self.rawchannel:
								print>>log, "[ABM-main][doTune] The active service was stopped, and the NIM is now free to use."
								current_slotid = slotid
							break
				else:
					print>>log, "[ABM-main][doTune] Nim found on slot id %d but it's busy. Stopping active service" % slotid
					self.postScanService = self.session.nav.getCurrentlyPlayingServiceReference()
					self.session.nav.stopService()
					self.rawchannel = resmanager.allocateRawChannel(slotid)
					if self.rawchannel:
						print>>log, "[ABM-main][doTune] The active service was stopped, and the NIM is now free to use."
						current_slotid = slotid

			if not self.rawchannel:
				if self.session.nav.RecordTimer.isRecording():
					print>>log, "[ABM-main][doTune] Cannot free NIM because a recording is in progress"
					self.showError(_('Cannot free NIM because a recording is in progress'))
					return
				else:
					print>>log, "[ABM-main][doTune] Cannot get the NIM"
					self.showError(_('Cannot get the NIM'))
					return

		# set extended timeout for rotors
		self.motorised = False
		if self.providers[self.currentAction]["streamtype"] == "dvbs" and self.isRotorSat(current_slotid, transponder["orbital_position"]):
			self.motorised = True
			self.LOCK_TIMEOUT = self.LOCK_TIMEOUT_ROTOR
			print>>log, "[ABM-main][doTune] Motorised dish. Will wait up to %i seconds for tuner lock." % (self.LOCK_TIMEOUT/10)
		else:
			self.LOCK_TIMEOUT = self.LOCK_TIMEOUT_FIXED
			print>>log, "[ABM-main][doTune] Fixed dish. Will wait up to %i seconds for tuner lock." % (self.LOCK_TIMEOUT/10)

		if not inStandby:
			self["tuner_text"].setText(chr(ord('A') + current_slotid))

		self.frontend = self.rawchannel.getFrontend()
		if not self.frontend:
			print>>log, "[ABM-main][doTune] Cannot get frontend"
			self.showError(_('Cannot get frontend'))
			return

		demuxer_id = self.rawchannel.reserveDemux()
		if demuxer_id < 0:
			print>>log, "[ABM-main][doTune] Cannot allocate the demuxer."
			self.showError(_('Cannot allocate the demuxer.'))
			return

		if self.providers[self.currentAction]["streamtype"] == "dvbs":
			params = eDVBFrontendParametersSatellite()
			params.frequency = transponder["frequency"]
			params.symbol_rate = transponder["symbol_rate"]
			params.polarisation = transponder["polarization"]
			params.fec = transponder["fec_inner"]
			params.inversion = transponder["inversion"]
			params.orbital_position = transponder["orbital_position"]
			params.system = transponder["system"]
			params.modulation = transponder["modulation"]
			params.rolloff = transponder["roll_off"]
			params.pilot = transponder["pilot"]
			if hasattr(eDVBFrontendParametersSatellite, "No_Stream_Id_Filter"):
				params.is_id = eDVBFrontendParametersSatellite.No_Stream_Id_Filter
			if hasattr(eDVBFrontendParametersSatellite, "PLS_Gold"):
				params.pls_mode = eDVBFrontendParametersSatellite.PLS_Gold
			if hasattr(eDVBFrontendParametersSatellite, "PLS_Default_Gold_Code"):
				params.pls_code = eDVBFrontendParametersSatellite.PLS_Default_Gold_Code
			if hasattr(eDVBFrontendParametersSatellite, "No_T2MI_PLP_Id"):
				params.t2mi_plp_id = eDVBFrontendParametersSatellite.No_T2MI_PLP_Id
			if hasattr(eDVBFrontendParametersSatellite, "T2MI_Default_Pid"):
				params.t2mi_pid = eDVBFrontendParametersSatellite.T2MI_Default_Pid
			params_fe = eDVBFrontendParameters()
			params_fe.setDVBS(params, False)

		elif self.providers[self.currentAction]["streamtype"] == "dvbt":
			params = eDVBFrontendParametersTerrestrial()
			params.frequency = transponder["frequency"]
			params.bandwidth = transponder["bandwidth"]
			params.code_rate_hp = transponder["code_rate_hp"]
			params.code_rate_lp = transponder["code_rate_lp"]
			params.inversion = transponder["inversion"]
			params.system = transponder["system"]
			params.modulation = transponder["modulation"]
			params.transmission_mode = transponder["transmission_mode"]
			params.guard_interval = transponder["guard_interval"]
			params.hierarchy = transponder["hierarchy"]
			params_fe = eDVBFrontendParameters()
			params_fe.setDVBT(params)

		elif self.providers[self.currentAction]["streamtype"] == "dvbc":
			params = eDVBFrontendParametersCable()
			params.frequency = transponder["frequency"]
			params.symbol_rate = transponder["symbol_rate"]
			params.fec_inner = transponder["fec_inner"]
			params.inversion = transponder["inversion"]
			params.modulation = transponder["modulation"]
			params_fe = eDVBFrontendParameters()
			params_fe.setDVBC(params)

		try:
			self.rawchannel.requestTsidOnid()
		except (TypeError):
			# for compatibility with some third party images
			self.rawchannel.requestTsidOnid(self.gotTsidOnid)

		self.frontend.tune(params_fe)
		self.manager.setAdapter(0)	# FIX: use the correct device
		self.manager.setDemuxer(demuxer_id)
		self.manager.setFrontend(current_slotid)

		self.current_slotid = current_slotid
		self.lockcounter = 0
		self.locktimer = eTimer()
		self.locktimer.callback.append(self.checkTunerLock)
		self.locktimer.start(100, 1)

	def checkTunerLock(self):
		from Screens.Standby import inStandby
		dict = {}
		self.frontend.getFrontendStatus(dict)
		if dict["tuner_state"] == "TUNING":
			print>>log, "[ABM-main][checkTunerLock] TUNING"
		elif dict["tuner_state"] == "LOCKED":
			print>>log, "[ABM-main][checkTunerLock] ACQUIRING TSID/ONID"
			self.progresscurrent += 1
			if not inStandby:
				self["progress_text"].value = self.progresscurrent
				self["progress"].setValue(self.progresscurrent)
				self["action"].setText(_("Reading %s...") % str(self.providers[self.currentAction]["name"]))
				self["status"].setText(_("Services: %d video - %d radio") % (self.manager.getServiceVideoRead(), self.manager.getServiceAudioRead()))
			self.timer = eTimer()
			self.timer.callback.append(self.doScan)
			self.timer.start(100, 1)
			return
		elif dict["tuner_state"] == "LOSTLOCK":
			print>>log, "[ABM-main][checkTunerLock] LOSTLOCK"
		elif dict["tuner_state"] == "FAILED":
			print>>log, "[ABM-main][checkTunerLock] TUNING FAILED FATAL"
			self.showError(_('Failed to tune %s on tuner %s.\n\nPlease check the following:\nThe tuner is correctly configured.\nYou can receive the specified frequency.') % (str(self.providers[self.currentAction]["name"]), chr(ord('A') + self.current_slotid)))
			return

		self.lockcounter += 1
		if self.lockcounter > self.LOCK_TIMEOUT:
			print>>log, "[AutoBouquetsMaker] Timeout for tuner lock, "
			self.showError(_('Timed out tuning %s on tuner %s.\n\nPlease check the following:\nThe tuner is correctly configured.\nYou can receive the specified frequency.') % (str(self.providers[self.currentAction]["name"]), chr(ord('A') + self.current_slotid)))
			return

		self.locktimer.start(100, 1)

	# for compatibility with some third party images
	def gotTsidOnid(self, tsid, onid):
		print>>log, "[ABM-main][gotTsidOnid] tsid, onid:", tsid, onid

		INTERNAL_PID_STATUS_NOOP = 0
		INTERNAL_PID_STATUS_WAITING = 1
		INTERNAL_PID_STATUS_SUCCESSFUL = 2
		INTERNAL_PID_STATUS_FAILED = 3

		if tsid is not None and onid is not None:
			self.pidStatus = INTERNAL_PID_STATUS_SUCCESSFUL
			self.tsid = tsid
			self.onid = onid
		else:
			self.pidStatus = INTERNAL_PID_STATUS_FAILED
			self.tsid = -1
			self.onid = -1
		self.timer.start(100, True)

	def doScan(self):
		if not self.manager.read(self.selectedProviders[self.currentAction], self.providers, self.motorised):
			print>>log, "[ABM-main][doScan] Cannot read data"
			self.showError(_('Cannot read data'))
			return
		self.doActions()

	def doBuildIndex(self):
		self.manager.save(self.providers, self.dependents)
		self.scanComplete()

	def scanComplete(self):
		from Screens.Standby import inStandby
		self.releaseFrontend()
		self.restartService()

		eDVBDB.getInstance().reloadServicelist()
		eDVBDB.getInstance().reloadBouquets()
		self.progresscurrent += 1
		if not inStandby:
			self["progress_text"].value = self.progresscurrent
			self["progress"].setValue(self.progresscurrent)
			self["action"].setText(_('Done'))
			self["status"].setText(_("Services: %d video - %d radio") % (self.manager.getServiceVideoRead(), self.manager.getServiceAudioRead()))

		self.timer = eTimer()
		self.timer.callback.append(self.close)
		self.timer.start(2000, 1)

	def releaseFrontend(self):
		if hasattr(self, 'frontend'):
			del self.frontend
		if hasattr(self, 'rawchannel'):
			del self.rawchannel
		self.frontend = None
		self.rawchannel = None

	def restartService(self):
		if self.postScanService:
			self.session.nav.playService(self.postScanService)
			self.postScanService = None
	
	def isRotorSat(self, slot, orb_pos):
		rotorSatsForNim = nimmanager.getRotorSatListForNim(slot)
		if len(rotorSatsForNim) > 0:
			for sat in rotorSatsForNim:
				if sat[0] == orb_pos:
					return True
		return False

	def printconfig(self):
		print>>log, "[ABM-config] level: ",config.autobouquetsmaker.level.value
		print>>log, "[ABM-config] providers: ",config.autobouquetsmaker.providers.value
		if config.autobouquetsmaker.bouquetsorder.value:
			print>>log, "[ABM-config] bouquetsorder: ",config.autobouquetsmaker.bouquetsorder.value
		if config.autobouquetsmaker.keepallbouquets.value:
			print>>log, "[ABM-config] keepbouquets: All"
		else:
			print>>log, "[ABM-config] keepbouquets: ",config.autobouquetsmaker.keepbouquets.value
		if config.autobouquetsmaker.hidesections.value:
			print>>log, "[ABM-config] hidesections: ",config.autobouquetsmaker.hidesections.value
		print>>log, "[ABM-config] add provider prefix: ",config.autobouquetsmaker.addprefix.value
		print>>log, "[ABM-config] show in extensions menu: ",config.autobouquetsmaker.extensions.value
		print>>log, "[ABM-config] placement: ",config.autobouquetsmaker.placement.value
		print>>log, "[ABM-config] skip services on non-configured satellites: ",config.autobouquetsmaker.skipservices.value
		print>>log, "[ABM-config] show non-indexed: ",config.autobouquetsmaker.showextraservices.value
		if config.autobouquetsmaker.FTA_only.value:
			print>>log, "[ABM-config] FTA_only: ",config.autobouquetsmaker.FTA_only.value
		print>>log, "[ABM-config] schedule: ",config.autobouquetsmaker.schedule.value
		if config.autobouquetsmaker.schedule.value:
			print>>log, "[ABM-config] schedule time: ",config.autobouquetsmaker.scheduletime.value
			print>>log, "[ABM-config] schedule days: ", [("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")[i] for i in range(7) if config.autobouquetsmaker.days[i].value]

	def getABMsettings(self):
		providers_extra = []
		providers_tmp = config.autobouquetsmaker.providers.value.split("|")
		for provider_str in providers_tmp:
			provider = provider_str.split(":", 1)[0]
			if provider in self.dependents:
				for descendent in self.dependents[provider]:
					providers_extra.append('|' + descendent + ':' + provider_str.split(":", 1)[1])
		return config.autobouquetsmaker.providers.value + ''.join(providers_extra)

	def about(self):
		self.session.open(MessageBox,"AutoBouquetsMaker\nVersion date - 21/10/2012\n\nCoded by:\n\nSkaman and AndyBlac",MessageBox.TYPE_INFO)

	def help(self):
		self.session.open(MessageBox,"AutoBouquetsMaker\nto be coded.",MessageBox.TYPE_INFO)

	def cancel(self):
		self.close(None)


autoScheduleTimer = None
def Scheduleautostart(reason, session=None, **kwargs):
	#
	# This gets called twice at start up,once by WHERE_AUTOSTART without session,
	# and once by WHERE_SESSIONSTART with session. WHERE_AUTOSTART is needed though
	# as it is used to wake from deep standby. We need to read from session so if
	# session is not set just return and wait for the second call to this function.
	#
	# Called with reason=1 during /sbin/shutdown.sysvinit, and with reason=0 at startup.
	# Called with reason=1 only happens when using WHERE_AUTOSTART.
	# If only using WHERE_SESSIONSTART there is no call to this function on shutdown.
	#
	print>>log, "[ABM-Scheduler][Scheduleautostart] reason(%d), session" % reason, session
	if reason == 0 and session is None:
		return
	global autoScheduleTimer
	global wasScheduleTimerWakeup
	wasScheduleTimerWakeup = False
	now = int(time())
	if reason == 0:
		if config.autobouquetsmaker.schedule.value:
			# check if box was woken up by a timer, if so, check if this plugin set this timer. This is not conclusive.
			if session.nav.wasTimerWakeup() and abs(config.autobouquetsmaker.nextscheduletime.value - time()) <= 450:
				wasScheduleTimerWakeup = True
				# if box is not in standby do it now
				from Screens.Standby import Standby, inStandby
				if not inStandby:
					# hack alert: session requires "pipshown" to avoid a crash in standby.py
					if not hasattr(session, "pipshown"):
						session.pipshown = False
					from Tools import Notifications
					Notifications.AddNotificationWithID("Standby", Standby)

		print>>log, "[ABM-Scheduler][Scheduleautostart] AutoStart Enabled"
		if autoScheduleTimer is None:
			autoScheduleTimer = AutoScheduleTimer(session)
	else:
		print>>log, "[ABM-Scheduler][Scheduleautostart] Stop"
		if autoScheduleTimer is not None:
			autoScheduleTimer.schedulestop()

class AutoScheduleTimer:
	instance = None
	def __init__(self, session):
		self.schedulename = "ABM-Scheduler"
		self.config = config.autobouquetsmaker
		self.itemtorun = AutoBouquetsMaker
		self.session = session
		self.scheduletimer = eTimer()
		self.scheduletimer.callback.append(self.ScheduleonTimer)
		self.scheduleactivityTimer = eTimer()
		self.scheduleactivityTimer.timeout.get().append(self.scheduledatedelay)
		self.ScheduleTime = 0
		now = int(time())
		if self.config.schedule.value:
			print>>log, "[%s][AutoScheduleTimer] Schedule Enabled at " % self.schedulename, strftime("%c", localtime(now))
			if now > 1546300800: # Tuesday, January 1, 2019 12:00:00 AM
				self.scheduledate()
			else:
				print>>log, "[%s][AutoScheduleTimer] STB clock not yet set." % self.schedulename
				self.scheduleactivityTimer.start(36000)
		else:
			print>>log, "[%s][AutoScheduleTimer] Schedule Disabled at" % self.schedulename, strftime("%c", localtime(now))
			self.scheduleactivityTimer.stop()

		assert AutoScheduleTimer.instance is None, "class AutoScheduleTimer is a singleton class and just one instance of this class is allowed!"
		AutoScheduleTimer.instance = self

	def __onClose(self):
		AutoScheduleTimer.instance = None

	def scheduledatedelay(self):
		self.scheduleactivityTimer.stop()
		self.scheduledate()

	def getScheduleTime(self):
		now = localtime(time())
		return int(mktime((now.tm_year, now.tm_mon, now.tm_mday, self.config.scheduletime.value[0], self.config.scheduletime.value[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

	def getScheduleDayOfWeek(self):
		today = self.getToday()
		for i in range(1, 8):
			if self.config.days[(today+i)%7].value:
				return i

	def getToday(self):
		return localtime(time()).tm_wday

	def scheduledate(self, atLeast = 0):
		self.scheduletimer.stop()
		self.ScheduleTime = self.getScheduleTime()
		now = int(time())
		if self.ScheduleTime > 0:
			if self.ScheduleTime < now + atLeast:
				self.ScheduleTime += 86400*self.getScheduleDayOfWeek()
			elif not self.config.days[self.getToday()].value:
				self.ScheduleTime += 86400*self.getScheduleDayOfWeek()
			next = self.ScheduleTime - now
			self.scheduletimer.startLongTimer(next)
		else:
			self.ScheduleTime = -1
		print>>log, "[%s][scheduledate] Time set to" % self.schedulename, strftime("%c", localtime(self.ScheduleTime)), strftime("(now=%c)", localtime(now))
		self.config.nextscheduletime.value = self.ScheduleTime
		self.config.nextscheduletime.save()
		configfile.save()
		return self.ScheduleTime

	def schedulestop(self):
		self.scheduletimer.stop()

	def ScheduleonTimer(self):
		self.scheduletimer.stop()
		now = int(time())
		wake = self.getScheduleTime()
		atLeast = 0
		if wake - now < 60:
			atLeast = 60
			print>>log, "[%s][ScheduleonTimer] onTimer occured at" % self.schedulename, strftime("%c", localtime(now))
			from Screens.Standby import inStandby
			if not inStandby:
				message = _("%s update is about to start.\nDo you want to allow this?") % self.schedulename
				ybox = self.session.openWithCallback(self.doSchedule, MessageBox, message, MessageBox.TYPE_YESNO, timeout = 30)
				ybox.setTitle(_('%s scheduled update') % self.schedulename)
			else:
				self.doSchedule(True)
		self.scheduledate(atLeast)

	def doSchedule(self, answer):
		now = int(time())
		if answer is False:
			if self.config.retrycount.value < 2:
				print>>log, "[%s][doSchedule] Schedule delayed." % self.schedulename
				self.config.retrycount.value += 1
				self.ScheduleTime = now + (int(self.config.retry.value) * 60)
				print>>log, "[%s][doSchedule] Time now set to" % self.schedulename, strftime("%c", localtime(self.ScheduleTime)), strftime("(now=%c)", localtime(now))
				self.scheduletimer.startLongTimer(int(self.config.retry.value) * 60)
			else:
				atLeast = 60
				print>>log, "[%s][doSchedule] Enough Retries, delaying till next schedule." % self.schedulename, strftime("%c", localtime(now))
				self.session.open(MessageBox, _("Enough Retries, delaying till next schedule."), MessageBox.TYPE_INFO, timeout = 10)
				self.config.retrycount.value = 0
				self.scheduledate(atLeast)
		else:
			self.timer = eTimer()
			self.timer.callback.append(self.runscheduleditem)
			print>>log, "[%s][doSchedule] Running Schedule" % self.schedulename, strftime("%c", localtime(now))
			self.timer.start(100, 1)

	def runscheduleditem(self):
		self.session.openWithCallback(self.runscheduleditemCallback, self.itemtorun)

	def runscheduleditemCallback(self):
		from Screens.Standby import Standby, inStandby, TryQuitMainloop, inTryQuitMainloop
		print>>log, "[%s][runscheduleditemCallback] inStandby" % self.schedulename, inStandby
		if self.config.schedule.value and wasScheduleTimerWakeup and inStandby and self.config.scheduleshutdown.value and not self.session.nav.getRecordings() and not inTryQuitMainloop:
			print>>log, "[%s] Returning to deep standby after scheduled wakeup" % self.schedulename
			self.session.open(TryQuitMainloop, 1)

	def doneConfiguring(self): # called from plugin on save
		now = int(time())
		if self.config.schedule.value:
			if autoScheduleTimer is not None:
				print>>log, "[%s][doneConfiguring] Schedule Enabled at" % self.schedulename, strftime("%c", localtime(now))
				autoScheduleTimer.scheduledate()
		else:
			if autoScheduleTimer is not None:
				self.ScheduleTime = 0
				print>>log, "[%s][doneConfiguring] Schedule Disabled at" % self.schedulename, strftime("%c", localtime(now))
				autoScheduleTimer.schedulestop()
		# scheduletext is not used for anything but could be returned to the calling function to display in the GUI.
		if self.ScheduleTime > 0:
			t = localtime(self.ScheduleTime)
			scheduletext = strftime(_("%a %e %b  %-H:%M"), t)
		else:
			scheduletext = ""
		return scheduletext

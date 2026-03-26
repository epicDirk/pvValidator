"""pvValidator orchestrator — coordinates parsing, rules, API validation, and output.

This module was originally a 765-LOC God Class. It now delegates to:
- parser.py: PV format parsing
- rules.py: Validation rule checks
- naming_client.py: ESS Naming Service API
- rule_loader.py: YAML rule configuration
- reporter.py: JSON/HTML output

The legacy interface (VFormD, VRuleD, VWarnD, VNameD, datainfo, PVDict)
is preserved for backwards compatibility with tabview.py and existing tests.
"""

import csv
import logging
import re
import sys

import requests

from pvValidatorUtils import epicsUtils, msiUtils, tabview
from pvValidatorUtils.exceptions import (
    MacroSubstitutionError,
    NamingServiceConnectionError,
)
from pvValidatorUtils.naming_client import NamingServiceClient
from pvValidatorUtils.parser import parse_pv
from pvValidatorUtils.rule_loader import RuleConfig
from pvValidatorUtils.rules import (
    KNOWN_SHORT_PROPERTIES,
    MAX_PROP_RECOMMENDED,
    Severity,
    check_all_rules,
    check_property_uniqueness,
    check_element_characters,
    check_element_lengths,
    check_device_index,
    check_legacy_prefix,
    effective_property_length,
)

logger = logging.getLogger("pvvalidator")

# Regex to extract PV name from EPICS record() declarations
# Matches: record(type, "PVname") — handles any whitespace
RECORD_PATTERN = re.compile(r'record\s*\(\s*\w+\s*,\s*"([^"]+)"\s*\)')


class pvUtils:
    """Orchestrator for PV validation.

    Coordinates format parsing, property rule checks, and Naming Service
    validation. Produces output via tabview (TUI), CSV, or stdout.
    """

    def __init__(
        self,
        pvepics=None,
        namingservice="prod",
        checkonlyfmt=False,
        pvfile=None,
        csvfile=None,
        epicsdb=None,
        msiobj=None,
        stdout=False,
    ):
        self.pvepics = pvepics
        self.namingservice = namingservice
        self.checkonlyfmt = checkonlyfmt
        self.pvfile = pvfile
        self.csvfile = csvfile
        self.epicsdb = epicsdb
        self.msiobj = msiobj
        self.stdout = stdout

        # Metadata
        self._getMeta()
        self.exiterror = False
        self.infovalidation = ""

        # Rule configuration (from YAML)
        self.config = RuleConfig()

        # Naming Service client
        self.api_client = NamingServiceClient(environment=namingservice)
        self._checkNamingService()

        # Load PV list from input sources
        self._checkPVFile()
        self._checkEPICSDBFile()
        self._checkSUBSFile()

        # PV list and output setup
        self.pvlist = self.pvepics.pvstringlist
        self.address = self.pvepics.getAddress
        self.header = [
            "System", "Subsystem", "Discipline", "Device",
            "Index", "Property", "PV Name", "Validation Comment",
        ]
        self.sumtitle = "PV Summary"
        self.ioctitle = "Validation Summary"
        self.data = []
        self.Title = f"pvValidator {self.version}"
        self.Widths = [6, 9, 10, 6, 6, 25, 60, 30]
        # Legacy state tracking (preserved for backwards compat with tests + tabview)
        self.datainfo = {}
        self.PVDict = {}
        self.VFormD = {}
        self.VRuleD = {}
        self.VWarnD = {}
        self.VNameD = {}
        self.SysStructCheckList = {}
        self.DevStructCheckList = {}
        self.EssNameCheckList = {}
        self.PVRuleFail = 0
        self.PVInternal = 0
        self.PVRuleWarn = 0
        self.PVWrongFormat = 0
        self.PVNotValid = 0
        self.PVNotRegistered = 0
        self.PVTot = len(self.pvepics.pvstringlist)
        self.charnotallow = set("!@$%^&*()+={}[]|\\:;'\"<>,.?/~`")

    # =================================================================
    # Main entry point
    # =================================================================

    def run(self):
        """Run the PV Validation pipeline."""
        self.data.append(self.header)

        self._checkValidFormat()
        self._checkPropRules()
        if not self.checkonlyfmt:
            self._checkValidName()

        # Build output table
        for pv in self.pvlist:
            _data = []
            comm = self._determineComment(pv)

            if (not self.VFormD[pv]) or (
                (not self.checkonlyfmt) and (not self.VNameD.get(pv, True))
            ):
                _data += ["------" for _ in range(6)]
            elif self.VFormD[pv] and self.checkonlyfmt:
                _data += ["******" for _ in range(6)]
                apiskip = "Info: Skip Validation Check with Naming API"
                if apiskip not in self.datainfo[pv]:
                    self.datainfo[pv] += apiskip
            else:
                _data += self._getPVFormat(pv)

            _data.append(pv)
            _data.append(comm)
            self.data.append(_data)

        # Build summary
        self._buildSummary()

        # Output
        self._output()

    def _determineComment(self, pv):
        """Determine the validation comment for a PV (legacy output format)."""
        if not self.VFormD[pv]:
            self.PVNotValid += 1
            self.PVWrongFormat += 1
            self.exiterror = True
            return "NOT VALID (Wrong Format)"

        has_rule = self.VRuleD.get(pv, False)
        has_warn = self.VWarnD.get(pv, False)
        has_name = self.VNameD.get(pv, True) if not self.checkonlyfmt else None

        if self.checkonlyfmt:
            if not has_rule and not has_warn:
                self.PVRuleFail += 1
                self.exiterror = True
                return "OK Format, Rule Fail"
            elif has_rule:
                return "OK Format, OK Rule"
            elif has_warn:
                self.PVRuleWarn += 1
                return "OK Format, Warn Rule"

        # Online mode
        if has_warn and has_name:
            self.PVRuleWarn += 1
            return "VALID (Warn Rule)"
        elif has_rule and has_name:
            return "VALID"
        elif (has_rule or has_warn) and not has_name:
            self.PVNotValid += 1
            self.PVNotRegistered += 1
            if has_warn:
                self.PVRuleWarn += 1
            self.exiterror = True
            return "NOT VALID (Name Fail)"
        elif not has_rule and has_name:
            self.PVNotValid += 1
            self.PVRuleFail += 1
            self.exiterror = True
            return "NOT VALID (Rule Fail)"
        else:
            self.PVNotValid += 1
            self.PVRuleFail += 1
            self.PVNotRegistered += 1
            self.exiterror = True
            return "NOT VALID (Name and Rule Fail)"

    def _buildSummary(self):
        """Build the validation summary text."""
        if self.address:
            self.infovalidation += f"The PV list is taken from the server {self.address} to perform online validation\n"

        self.infovalidation += f"The Total PVs are = {self.PVTot}\n"
        if self.checkonlyfmt:
            self.infovalidation += "The Total Not Valid PVs are = **Not Evaluated**\n"
            self.infovalidation += "The PVs with NOT Registered Name are = **Not Evaluated**\n"
        else:
            self.infovalidation += f"The Total Not Valid PVs are = {self.PVNotValid}\n"
            self.infovalidation += f"The PVs with NOT Registered Name are = {self.PVNotRegistered}\n"
        self.infovalidation += f"The PVs with Wrong Format are = {self.PVWrongFormat}\n"
        self.infovalidation += f"The PVs with Rule Failure are = {self.PVRuleFail}\n"
        self.infovalidation += f"The PVs with Rule Warning are = {self.PVRuleWarn}\n"
        self.infovalidation += f"The PVs Internal are = {self.PVInternal}\n"

    def _output(self):
        """Write results to TUI, CSV, or stdout."""
        readme = (
            f"pvValidator {self.version}\n"
            f"Author: {self.author}\n"
            f"Author email: {self.email}\n"
            f"Platforms: {self.platform}\n"
            f"{self.epicsinfo}\n"
            f"{self.description}\n"
            f"pvValidator is released under the {self.license} license (ESS - 2021)\n"
        )

        datainfo = self._getDataInfo()
        if self.csvfile is None and not self.stdout:
            tabview.view(
                self.data,
                info=self.infovalidation,
                Title=self.Title,
                column_widths=self.Widths,
                datainfo=datainfo,
                sumtitle=self.sumtitle,
                ioctitle=self.ioctitle,
                readme=readme,
            )
        else:
            self.data[0].append(self.sumtitle)
            for j, d in enumerate(self.data):
                if j != 0:
                    self.data[j].append(datainfo[d[6]])

            if self.stdout:
                for d in self.data:
                    print(" ".join(d))
                print(self.ioctitle)
                print(self.infovalidation)
            else:
                self.data[0].append(self.ioctitle)
                self.data[1].append(self.infovalidation)
                with open(self.csvfile, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerows(self.data)
        if self.exiterror:
            raise SystemExit(1)

    # =================================================================
    # Naming Service (delegates to NamingServiceClient)
    # =================================================================

    def _checkNamingService(self):
        """Check Naming Service availability."""
        # Legacy URL attributes (still used by _checkValidName for compatibility)
        urls = self.api_client.DEFAULT_URLS
        url = urls.get(self.namingservice, urls["prod"])
        self.NameService = "Production" if self.namingservice == "prod" else "Testing"
        if not self.checkonlyfmt:
            try:
                self.api_client.check_connectivity()
                self.infovalidation += f"The Validation is done through {self.NameService} Naming Service\n"
            except NamingServiceConnectionError as e:
                logger.error(str(e))
                raise NamingServiceConnectionError(
                    f"Fail to connect to Naming Service {url}"
                ) from e
        else:
            self.infovalidation += "The Validation through Naming Service was skipped\n"

    def _checkValidName(self):
        """Validate PV names against the Naming Service (delegates to NamingServiceClient)."""
        for essname in self.PVDict.keys():
            s = essname.split(":")[0]
            try:
                sys_name, subsys = s.split("-")
            except ValueError:
                sys_name = s
                subsys = ""

            scheck = ""
            checkname = True
            nameok = False

            # System check
            if sys_name not in self.SysStructCheckList:
                self.SysStructCheckList[sys_name] = (
                    self.api_client.validate_system(sys_name)
                )
            if self.SysStructCheckList[sys_name] == False:
                scheck += f'Error: The System "{sys_name}" is not active in the Naming Service\n'
                checkname = False

            # Subsystem check
            if subsys:
                cache_key = f"{sys_name}-{subsys}"
                if cache_key not in self.SysStructCheckList:
                    self.SysStructCheckList[cache_key] = (
                        self.api_client.validate_subsystem(sys_name, subsys)
                    )
                if self.SysStructCheckList[cache_key] == False:
                    scheck += f'Error: The Subsystem "{subsys}" of the System "{sys_name}" is not active in the Naming Service\n'
                    checkname = False

            # Device structure check
            if not essname.endswith(":"):
                dev_part = essname.split(":")[1]
                parts = dev_part.split("-")
                if len(parts) >= 3:
                    dis, dev = parts[0], parts[1]
                    d = f"{dis}-{dev}"

                    if dev == "Virt":
                        scheck += f'Error: The Device "{dev}" of the Discipline "{dis}" is not valid\n'
                        checkname = False

                    if dis not in self.DevStructCheckList:
                        self.DevStructCheckList[dis] = (
                            self.api_client.validate_discipline(dis)
                        )
                    if self.DevStructCheckList[dis] == False:
                        scheck += f'Error: The Discipline "{dis}" is not active in the Naming Service\n'
                        checkname = False

                    if d not in self.DevStructCheckList:
                        self.DevStructCheckList[d] = (
                            self.api_client.validate_device(dis, dev)
                        )
                    if self.DevStructCheckList[d] == False:
                        scheck += f'Error: The Device "{dev}" of the Discipline "{dis}" is not active in the Naming Service\n'
                        checkname = False

                sname = essname
            else:
                sname = s

            # Full name registration check
            if checkname:
                if sname not in self.EssNameCheckList:
                    result = self.api_client.validate_name(sname)
                    nameok = result["registered"]
                    if result["registered"]:
                        scheck += f'Info: The Name "{sname}" is registered in the Naming Service\n'
                    else:
                        scheck += f'Error: {result["message"]}\n'
                    self.EssNameCheckList[sname] = nameok
                else:
                    nameok = self.EssNameCheckList[sname]

            # Apply to all PVs with this ESS name
            for prop in self.PVDict[essname]:
                pv = essname + ":" + prop
                if scheck not in self.datainfo.get(pv, ""):
                    self.datainfo[pv] = self.datainfo.get(pv, "") + scheck
                self.VNameD[pv] = checkname and nameok

    # =================================================================
    # Format validation (delegates to parser.py)
    # =================================================================

    def _checkValidFormat(self):
        """Check PV format and run structural element rules."""
        for pv in self.pvlist:
            components = parse_pv(pv)
            pvelem = components.to_list() if components else []
            if self._isValidFormat(pvelem, pv):
                self.VFormD[pv] = True
                dev, prop = pv.rsplit(":", 1)
                self.PVDict.setdefault(dev, []).append(prop)

                # Structural checks from rules module
                if components:
                    self._checkStructuralRules(pv, components)
            else:
                self.VFormD[pv] = False

    def _checkStructuralRules(self, pv, components):
        """Run element length, character, index, and legacy checks."""
        for check_fn in [check_element_lengths, check_element_characters, check_device_index, check_legacy_prefix]:
            for msg in check_fn(components):
                text = f"{msg.severity.value}: {msg.message}\n"
                if text not in self.datainfo.get(pv, ""):
                    self.datainfo[pv] = self.datainfo.get(pv, "") + text

    def _isValidFormat(self, pvelem, pv):
        if pvelem == []:
            self.datainfo[pv] = "Error: The PV does not follow any ESS Name Format\n"
            return False
        self.datainfo[pv] = "Info: The PV follows ESS Name Format\n"
        return True

    def _getPVFormat(self, pv):
        """Parse PV into [sys, sub, dis, dev, idx, prop] via parser module."""
        components = parse_pv(pv)
        if components is None:
            return []
        return components.to_list()

    def _getDataInfo(self):
        return self.datainfo

    # =================================================================
    # Property rules (uses new rules module for uniqueness check)
    # =================================================================

    def _checkPropRules(self):
        """Check property rules for each PV.

        Uses O(n) normalized uniqueness check from rules.py for confusable
        detection, plus individual property checks.
        """
        self.PVErrList = []
        self.PVWarnList = []
        TempErr = ["-Drv01-SyncErr-Alrm", "-Enc01-LtchAutRstSp"]
        tmperrmsg = "      !!!This issue is fixed since version 8 of ECMCCFG Module!!!Suggest to update your EPICS Module!!!\n"

        max_pv = self.config.max_pv_length
        max_prop = self.config.max_property_length
        min_prop_warn = self.config.min_property_length_warn

        for dev, plist in self.PVDict.items():
            # O(n) confusable uniqueness check (replaces O(n²) itertools.combinations)
            uniqueness_msgs = check_property_uniqueness(dev, plist)
            for pv_key, msgs in uniqueness_msgs.items():
                for msg in msgs:
                    if msg.severity == Severity.ERROR:
                        self._checkDataMsg(pv1=pv_key, err1=f"Error: {msg.message}\n")

            # Per-property checks
            for prop in plist:
                pv = dev + ":" + prop

                if len(pv) > max_pv:
                    self._checkDataMsg(pv1=pv, err1=f"Error: The PV is beyond {max_pv} characters\n")

                if len(prop) == 0:
                    self._checkDataMsg(pv1=pv, err1="Error: The PV Property is missing\n")

                prop_eff_len = effective_property_length(prop)
                if prop_eff_len > max_prop:
                    errmsg = f"Error: The PV Property is beyond {max_prop} characters ({prop_eff_len})\n"
                    if (TempErr[0] in prop) or (TempErr[1] in prop):
                        errmsg += tmperrmsg
                    self._checkDataMsg(pv1=pv, err1=errmsg)
                elif prop_eff_len > MAX_PROP_RECOMMENDED:
                    self._checkDataMsg(pv1=pv, warn1=f"Warning: The PV Property exceeds recommended {MAX_PROP_RECOMMENDED} characters ({prop_eff_len})\n")

                if prop.endswith("-S") or prop.endswith("_S"):
                    self._checkDataMsg(pv1=pv, err1="Error: The PV Property for a Setpoint value should end with -SP\n")

                if prop.endswith("-R") or prop.endswith("_R"):
                    self._checkDataMsg(pv1=pv, err1="Error: The PV Property for a Reading value should not contain any suffix\n")

                if prop.endswith("-RBV") or prop.endswith("_RBV"):
                    self._checkDataMsg(pv1=pv, err1="Error: The PV Property for a Readback value should end with -RB\n")

                if 0 < prop_eff_len < min_prop_warn:
                    clean = prop.lstrip("#")
                    if clean not in KNOWN_SHORT_PROPERTIES:
                        self._checkDataMsg(pv1=pv, warn1=f"Warning: The PV Property is below {min_prop_warn} characters ({prop_eff_len})\n")

                if any(c in self.charnotallow for c in prop):
                    self._checkDataMsg(pv1=pv, err1="Error: The PV Property contains not allowed character(s)\n")

                if "#" in prop:
                    if prop.startswith("#"):
                        self._checkDataMsg(pv1=pv, info1='Info: The PV is an "Internal PV"\n')
                    else:
                        self._checkDataMsg(pv1=pv, err1="Error: The PV Property contains the # character in not allowed position\n")

                if len(prop) > 0 and (
                    prop[0].isdigit() or prop[0] in self.charnotallow or prop[0] in ("_", "-")
                ):
                    self._checkDataMsg(pv1=pv, err1="Error: The PV Property does not start alphabetical\n")
                if len(prop) > 0 and prop[0].islower():
                    self._checkDataMsg(pv1=pv, warn1="Warning: The PV Property does not start in upper case\n")

        # Finalize rule/warn status
        for dev, plist in self.PVDict.items():
            for prop in plist:
                pv = dev + ":" + prop
                if pv in self.PVErrList:
                    self.VRuleD[pv] = False
                    self.VWarnD[pv] = False
                elif pv in self.PVWarnList:
                    self.VRuleD[pv] = False
                    self.VWarnD[pv] = True
                else:
                    self.VWarnD[pv] = False
                    self.VRuleD[pv] = True
                if pv not in self.PVWarnList and pv not in self.PVErrList:
                    self.datainfo[pv] += "Info: The PV follows ESS PV Property Rules\n"

    def _checkDataMsg(self, pv1=None, err1=None, warn1=None, info1=None, pv2=None, err2=None):
        """Track errors and warnings per PV."""
        if pv1 is not None:
            if err1 is not None and err1 not in self.datainfo.get(pv1, ""):
                self.datainfo[pv1] = self.datainfo.get(pv1, "") + err1
                if pv1 not in self.PVErrList:
                    self.PVErrList.append(pv1)
            if warn1 is not None and warn1 not in self.datainfo.get(pv1, ""):
                self.datainfo[pv1] = self.datainfo.get(pv1, "") + warn1
                if pv1 not in self.PVWarnList:
                    self.PVWarnList.append(pv1)
            if info1 is not None and info1 not in self.datainfo.get(pv1, ""):
                self.datainfo[pv1] = self.datainfo.get(pv1, "") + info1
                self.PVInternal += 1
        if pv2 is not None:
            if err2 is not None and err2 not in self.datainfo.get(pv2, ""):
                self.datainfo[pv2] = self.datainfo.get(pv2, "") + err2
                if pv2 not in self.PVErrList:
                    self.PVErrList.append(pv2)

    # =================================================================
    # Input loading (unchanged — touches SWIG/C++ boundary)
    # =================================================================

    def _checkPVFile(self):
        """Load PVs from a plain text file."""
        if self.pvfile is None:
            return
        with open(self.pvfile, "r") as pvf:
            for lin in pvf:
                if not lin.startswith("%") and not lin.startswith("#") and lin.strip():
                    self.pvepics.pvstringlist.push_back(lin.strip().split()[0])
        self.infovalidation += f"The PV list is taken from the file {self.pvfile} to perform offline validation\n"

    def _checkEPICSDBFile(self):
        """Load PVs from an EPICS database file with optional macros."""
        if self.epicsdb is None:
            return
        listdb = []
        epicsdbfile = self.epicsdb[0]
        with open(epicsdbfile, "r") as fdb:
            for r in fdb:
                if r.lstrip().startswith("#"):
                    continue
                m = RECORD_PATTERN.search(r)
                if m:
                    listdb.append(m.group(1))
        if len(self.epicsdb) == 2:
            macrovar = self.epicsdb[1]
            for m in macrovar.split(","):
                if "=" not in m:
                    raise MacroSubstitutionError(
                        f"Invalid macro definition '{m.strip()}' — expected KEY=VALUE format"
                    )
                k, v = m.split("=", 1)
                listdb = [ll.replace("$(" + k.strip() + ")", v.strip()) for ll in listdb]
        if any("$" in s for s in listdb):
            raise MacroSubstitutionError(
                f"Missing macro definitions for {epicsdbfile}, please check!"
            )
        for ldb in listdb:
            self.pvepics.pvstringlist.push_back(ldb)
        self.infovalidation += f"The PV list is taken from the EPICS DB {epicsdbfile} file to perform offline validation\n"

    def _checkSUBSFile(self):
        """Load PVs from an EPICS substitutions file via MSI."""
        if self.msiobj is None:
            return
        listdb = []
        msisubsfile = self.msiobj[0]
        msipath = "."
        msivar = ""
        if len(self.msiobj) == 2:
            if "=" not in self.msiobj[1]:
                msipath = self.msiobj[1]
            else:
                msivar = self.msiobj[1]
        if len(self.msiobj) == 3:
            msipath = self.msiobj[1]
            msivar = self.msiobj[2]
        msi = msiUtils.msiUtils(msisubsfile, msipath, msivar, True)
        msi.createDB()
        for r in msi.stringdb.splitlines():
            if r.lstrip().startswith("#"):
                continue
            m = RECORD_PATTERN.search(r)
            if m:
                listdb.append(m.group(1))
        if any("$" in s for s in listdb):
            raise MacroSubstitutionError(
                f"Missing macro definitions for {msisubsfile}, please check!"
            )
        for ldb in listdb:
            self.pvepics.pvstringlist.push_back(ldb)
        self.infovalidation += f"The PV list is taken expanding the substitution file {msisubsfile} to perform offline validation\n"

    # =================================================================
    # Metadata
    # =================================================================

    def _getMeta(self):
        """Load package metadata."""
        from importlib.metadata import metadata
        pkg = "pvValidatorUtils"
        meta = metadata(pkg)
        self.author = meta.get("Author-email").split(" <")[0]
        self.email = meta.get("Author-email").split()[2]
        self.version = meta.get("Version")
        self.license = meta.get("License")
        self.platform = meta.get_all("Platform")
        self.description = meta.get("Summary")
        self.epicsinfo = epicsUtils().getVersion

import csv
import itertools
import re
import sys

import requests

from pvValidatorUtils import epicsUtils, msiUtils, tabview

MAX_PV_LENGHT = 60
MAX_PROP_LENGHT = 25
MAX_PROP_WARN = 4


class pvUtils:
    """
    Class to declare the pvUtils object:

    pvepics --> epicsUtsils object: it contains the pvstringlist variable which can be filled from the IOC or from an input file (plain text, epics db or substitution)
    namingservice --> str: the naming service (default="prod" for production)
    checkonlyformat --> bool: if the validation via the naming service should be skipped (default=False)
    pvfile --> str: the name of the PV input plain text file
    csvfile --> str: the name of the output csv file to write the validation outcome
    epicsdb --> str: the name of the epics db, with the optional macro declaration
    msiobj --> str: the name of the substitution file, with the optional path to the template and macro declaration
    stdout --> bool: if the validation outcome should be written in the STDOUT (default=False)
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
        #####
        self._getMeta()
        self.exiterror = False
        self.pattern = "record"
        self.infovalidation = ""

        self._checkNamingService()

        self._checkPVFile()

        self._checkEPICSDBFile()

        self._checkSUBSFile()

        self.pvlist = self.pvepics.pvstringlist
        self.address = self.pvepics.getAddress
        self.header = [
            "System",
            "Subsystem",
            "Discipline",
            "Device",
            "Index",
            "Property",
            "PV Name",
            "Validation Comment",
        ]
        self.sumtitle = "PV Summary"
        self.ioctitle = "Validation Summary"
        self.data = []
        self.Title = f"pvValidator {self.version}"
        self.Widths = [6, 9, 10, 6, 6, 25, 60, 30]
        self.headers = {"accept": "application/json"}
        self.exist = 1
        self.notexist = 0
        self.empty = 2
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

    def run(self):
        """Run the PV Validation"""
        self.data.append(self.header)

        comm = None

        self._checkValidFormat()
        self._checkPropRules()
        if not self.checkonlyfmt:
            self._checkValidName()

        for pv in self.pvlist:
            _data = []

            if (not self.VFormD[pv]) or (
                (not self.checkonlyfmt) and (not self.VNameD[pv])
            ):
                _data += ["------" for _ in range(6)]
            elif self.VFormD[pv] and (self.checkonlyfmt):
                _data += ["******" for _ in range(6)]
                apiskip = "Info: Skip Validation Check with Naming API"
                if apiskip not in self.datainfo[pv]:
                    self.datainfo[pv] += apiskip
            else:
                _data += self._getPVFormat(pv)

            if not self.VFormD[pv]:
                comm = "NOT VALID (Wrong Format)"
                self.PVNotValid += 1
                self.PVWrongFormat += 1
                self.exiterror = True
            elif (
                self.VFormD[pv]
                and (not self.VRuleD[pv])
                and (not self.VWarnD[pv])
                and self.checkonlyfmt
            ):
                comm = "OK Format, Rule Fail"
                self.PVRuleFail += 1
                self.exiterror = True
            elif self.VFormD[pv] and self.VRuleD[pv] and self.checkonlyfmt:
                comm = "OK Format, OK Rule"
            elif self.VFormD[pv] and self.VWarnD[pv] and self.checkonlyfmt:
                comm = "OK Format, Warn Rule"
                self.PVRuleWarn += 1
            elif (
                self.VFormD[pv]
                and self.VWarnD[pv]
                and ((not self.checkonlyfmt) and self.VNameD[pv])
            ):
                comm = "VALID (Warn Rule)"
                self.PVRuleWarn += 1
            elif (
                self.VFormD[pv]
                and self.VRuleD[pv]
                and ((not self.checkonlyfmt) and self.VNameD[pv])
            ):
                comm = "VALID"
            elif (
                self.VFormD[pv]
                and (self.VRuleD[pv] or self.VWarnD[pv])
                and ((not self.checkonlyfmt) and (not self.VNameD[pv]))
            ):
                comm = "NOT VALID (Name Fail)"
                self.PVNotValid += 1
                self.PVNotRegistered += 1
                if self.VWarnD[pv]:
                    self.PVRuleWarn += 1
                self.exiterror = True

            elif (
                self.VFormD[pv]
                and (not self.VRuleD[pv])
                and ((not self.checkonlyfmt) and self.VNameD[pv])
            ):
                comm = "NOT VALID (Rule Fail)"
                self.PVNotValid += 1
                self.PVRuleFail += 1
                self.exiterror = True
            elif (
                self.VFormD[pv]
                and (not self.VRuleD[pv])
                and (not self.VWarnD[pv])
                and ((not self.checkonlyfmt) and (not self.VNameD[pv]))
            ):
                comm = "NOT VALID (Name and Rule Fail)"
                self.PVNotValid += 1
                self.PVRuleFail += 1
                self.PVNotRegistered += 1
                self.exiterror = True

            _data.append(pv)
            _data.append(comm)
            self.data.append(_data)

        if self.address:
            self.infovalidation += f"The PV list is taken from the server {self.address} to perform online validation\n"

        self.infovalidation += f"The Total PVs are = {self.PVTot}\n"
        if self.checkonlyfmt:
            self.infovalidation += "The Total Not Valid PVs are = **Not Evaluated**\n"
            self.infovalidation += (
                "The PVs with NOT Registered Name are = **Not Evaluated**\n"
            )
        else:
            self.infovalidation += f"The Total Not Valid PVs are = {self.PVNotValid}\n"
            self.infovalidation += (
                f"The PVs with NOT Registered Name are = {self.PVNotRegistered}\n"
            )
        self.infovalidation += f"The PVs with Wrong Format are = {self.PVWrongFormat}\n"
        self.infovalidation += f"The PVs with Rule Failure are = {self.PVRuleFail}\n"
        self.infovalidation += f"The PVs with Rule Warning are = {self.PVRuleWarn}\n"
        self.infovalidation += f"The PVs Internal are = {self.PVInternal}\n"
        readme = f"pvValidator {self.version}\n"
        readme += f"Author: {self.author}\n"
        readme += f"Author email: {self.email}\n"
        readme += f"Platforms: {self.platform}\n"
        readme += f"{self.epicsinfo}\n"
        readme += f"{self.description}\n"
        readme += (
            f"pvValidator is realeased under the {self.license} license (ESS - 2021)\n"
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
            sys.exit(1)

    def _checkNamingService(self):
        """Check the Naming Service (produtcion or test) availability"""
        urlinfo = {
            "test": ["https://naming-test-01.cslab.esss.lu.se/", "Testing"],
            "prod": ["https://naming.esss.lu.se/", "Production"],
        }
        url = urlinfo[self.namingservice][0]
        self.NameService = urlinfo[self.namingservice][1]
        self.urlparts = url + "rest/parts/mnemonic/"
        self.urlname = url + "rest/deviceNames/"
        if not self.checkonlyfmt:
            try:
                requests.head(url, timeout=1)
                self.infovalidation += f"The Validation is done through {self.NameService} Naming Service\n"
            except requests.exceptions.ConnectionError as e:
                print(e)
                print(f"Fail to connect to Naming Service {url}, exit!")
                sys.exit(1)
        else:
            self.infovalidation += "The Validation through Naming Service was skipped\n"

    def _checkPVFile(self):
        """Check if the PVs should be taken from a input text file, then fill the list"""
        if self.pvfile is None:
            return
        with open(self.pvfile, "r") as pvf:
            Lines = pvf.readlines()
        for lin in Lines:
            if not lin.startswith("%") and not lin.startswith("#") and lin.strip():
                self.pvepics.pvstringlist.push_back(lin.strip().split()[0])
        self.infovalidation += f"The PV list is taken from the file {self.pvfile} to perform offline validation\n"

    def _checkEPICSDBFile(self):
        """Check if the PVs should be taked from an EPICS database file, then fill the list after parsing it,
        the (optional) macro are passed as second argument and they should be declared as VAR=VALUE,...
        otherwise it will exit after warning
        """
        if self.epicsdb is None:
            return
        listdb = []
        epicsdbfile = self.epicsdb[0]  # input EPICS datbase file
        with open(epicsdbfile, "r") as fdb:
            for r in fdb:
                if (
                    self.pattern in r
                    and not r.lstrip().startswith("#")
                    and not r.lstrip().startswith("f")
                    and not r.lstrip().startswith("i")
                ):
                    listdb.append(
                        ((r.split(",")[1]).rsplit(")", 1)[0].strip()).strip(
                            '"'
                        )  # EPICS record parsing to take the pv name: record(ai, "mypv") --> "mypv"
                    )
        if len(self.epicsdb) == 2:  # some macro are defined, i.e. VAR=VALUE,...
            macrovar = self.epicsdb[1]  # macro definition
            mlist = macrovar.split(",")
            for m in mlist:
                k, v = m.split("=")
                listdb = [
                    ll.replace("$(" + k.split()[0] + ")", v.split()[0])
                    for ll in listdb  # macro substitution
                ]
        if any("$" in string for string in listdb):
            print(
                f"It seems that you miss some macro definition (VAR=VALUE,...) for your EPICS DB file {epicsdbfile}, please check! Exit!"
            )
            sys.exit(1)

        for ldb in listdb:
            self.pvepics.pvstringlist.push_back(ldb)

        self.infovalidation += f"The PV list is taken from the EPICS DB {epicsdbfile} file to perform offline validation\n"

    def _checkSUBSFile(self):
        """Check if the PVs should be taked from an EPICS subsitutiosn file,
        then fill the list after creating the EPICS database using the msi code and parsing it,
        the (optional) path to the template file(s) is passed as second argument,
        the (optional) macro are passed as third argument and they should be declared as VAR=VALUE,...
        otherwise it will exit after warning
        """
        if self.msiobj is None:
            return
        listdb = []
        msisubsfile = self.msiobj[0]  # input substitutions file
        msipath = "."  # default path to search the template file
        msivar = ""  # macro not defined
        if (
            len(self.msiobj) == 2
        ):  # a non default path to search the template is defined or the some macro are defined, i.e. VAR=VALUE,...
            if "=" not in self.msiobj[1]:  # only the non default path is defined
                msipath = self.msiobj[1]
            else:
                msivar = self.msiobj[
                    1
                ]  # some macro are defined and the default path is used
        if len(self.msiobj) == 3:  # both non-default path and macro are defined
            msipath = self.msiobj[1]  # non-default path
            msivar = self.msiobj[2]  # macro definition
        msi = msiUtils.msiUtils(
            msisubsfile, msipath, msivar, True
        )  # msi object declaration
        msi.createDB()  # create the EPICS database
        for r in msi.stringdb.splitlines():
            if (
                self.pattern in r
                and not r.lstrip().startswith("#")
                and not r.lstrip().startswith("f")
                and not r.lstrip().startswith("i")
            ):
                listdb.append(
                    ((r.split(",")[1]).rsplit(")", 1)[0].strip()).strip('"')
                )  # EPICS record parsing to take the pv name: record(ai, "mypv") --> "mypv"
        if any("$" in string for string in listdb):
            print(
                f"It seems that you miss some macro defintion (VAR=VALUE,...) for your substitution file {msisubsfile}, please check! Exit!"
            )
            sys.exit(1)
        for ldb in listdb:
            self.pvepics.pvstringlist.push_back(ldb)

        self.infovalidation += f"The PV list is taken expanding the substitution file {msisubsfile} to perform offline validation\n"

    def _getMeta(self):
        """Get the metadata information"""
        pkg = "pvValidatorUtils"
        if sys.version_info >= (3, 8, 0):
            from importlib.metadata import metadata

            meta = metadata(pkg)
            # split for the non-sense merging of name and email by pyproject.toml....
            self.author = meta.get("Author-email").split(" <")[0]
            self.email = meta.get("Author-email").split()[2]
        else:
            from email import message_from_string

            from pkg_resources import get_distribution

            dist = get_distribution(pkg)
            try:
                pkginfo = dist.get_metadata("METADATA")
            except FileNotFoundError:
                pkginfo = dist.get_metadata("PKG-INFO")
            meta = message_from_string(pkginfo)
            self.author = meta.get("Author")
            self.email = meta.get("Author-email")
        self.version = meta.get("Version")
        self.license = meta.get("License")
        self.platform = meta.get_all("Platform")
        self.description = meta.get("Summary")
        self.epicsinfo = epicsUtils().getVersion

    def _checkValidFormat(self):
        """Check if the PV has a valid format"""
        for pv in self.pvlist:
            pvelem = self._getPVFormat(pv)
            if self._isValidFormat(pvelem, pv):
                self.VFormD[pv] = True
                dev, prop = pv.rsplit(":", 1)
                self.PVDict.setdefault(dev, []).append(prop)
            else:
                self.VFormD[pv] = False

    def _getDataInfo(self):
        return self.datainfo

    def _isValidFormat(self, pvelem, pv):
        if pvelem == []:
            self.datainfo[pv] = "Error: The PV does not follow any ESS Name Format\n"
            return False
        else:
            self.datainfo[pv] = "Info: The PV follows ESS Name Format\n"
            return True

    def _checkDataMsg(
        self, pv1=None, err1=None, warn1=None, info1=None, pv2=None, err2=None
    ):
        """Fill the error and warnig list for each PV"""
        if pv1 is not None:
            if err1 is not None and err1 not in self.datainfo[pv1]:
                self.datainfo[pv1] += err1
                if pv1 not in self.PVErrList:
                    self.PVErrList.append(pv1)
            if warn1 is not None and warn1 not in self.datainfo[pv1]:
                self.datainfo[pv1] += warn1
                if pv1 not in self.PVWarnList:
                    self.PVWarnList.append(pv1)
            if info1 is not None and info1 not in self.datainfo[pv1]:
                self.datainfo[pv1] += info1
                self.PVInternal += 1

        if pv2 is not None:
            if err2 is not None and err2 not in self.datainfo[pv2]:
                self.datainfo[pv2] += err2
                if pv2 not in self.PVErrList:
                    self.PVErrList.append(pv2)

    def _getResp(self, endpoint):
        return requests.get(endpoint, headers=self.headers)

    def _checkPropRules(self):
        """Check the Property part of each PV"""
        self.PVErrList = []
        self.PVWarnList = []
        TempErr = ["-Drv01-SyncErr-Alrm", "-Enc01-LtchAutRstSp"]
        tmperrmsg = "      !!!This issue is fixed since version 8 of ECMCCFG Module!!!Suggest to update your EPICS Module!!!\n"
        errs = "Error: The PV Property is not unique"
        regex = "0+(?![_A-Za-z-])(?!$)"
        for dev, plist in self.PVDict.items():
            for p1, p2 in itertools.combinations(plist, 2):
                pv1 = dev + ":" + p1
                pv2 = dev + ":" + p2
                errmsgpv1 = ""
                errmsgpv2 = ""
                if p1 == p2:
                    errmsgpv1 = f"{errs} (duplication issue)\n"
                    self._checkDataMsg(pv1=pv1, err1=errmsgpv1)
                else:
                    if p1.lower() == p2.lower():
                        errmsgpv1 = f"{errs} (case issue, check {pv2})\n"
                        errmsgpv2 = f"{errs} (case issue, check {pv1})\n"
                        self._checkDataMsg(
                            pv1=pv1, pv2=pv2, err1=errmsgpv1, err2=errmsgpv2
                        )
                    if p1 == p2.replace("O", "0") or p1 == p2.replace("0", "O"):
                        errmsgpv1 = f"{errs} (0 O issue, check {pv2})\n"
                        errmsgpv2 = f"{errs} (0 O issue, check {pv2})\n"
                        self._checkDataMsg(
                            pv1=pv1, pv2=pv2, err1=errmsgpv1, err2=errmsgpv2
                        )
                    if p1 == p2.replace("VV", "W") or p1 == p2.replace("W", "VV"):
                        errmsgpv1 = f"{errs} (VV W issue, check {pv2})\n"
                        errmsgpv2 = f"{errs} (VV W issue, check {pv1})\n"
                        self._checkDataMsg(
                            pv1=pv1, pv2=pv2, err1=errmsgpv1, err2=errmsgpv2
                        )
                    if p1 == p2.replace("1", "I") or p1 == p2.replace("I", "1"):
                        errmsgpv1 = f"{errs} (1 I issue, check {pv2})\n"
                        errmsgpv2 = f"{errs} (1 I issue, check {pv1})\n"
                        self._checkDataMsg(
                            pv1=pv1, pv2=pv2, err1=errmsgpv1, err2=errmsgpv2
                        )
                    if p1 == p2.replace("1", "l") or p1 == p2.replace("l", "1"):
                        errmsgpv1 = f"{errs} (1 l issue, check {pv2})\n"
                        errmsgpv2 = f"{errs} (1 l issue, check {pv1})\n"
                        self._checkDataMsg(
                            pv1=pv1, pv2=pv2, err1=errmsgpv1, err2=errmsgpv2
                        )
                    if p1 == p2.replace("I", "l") or p1 == p2.replace("l", "I"):
                        errmsgpv1 = f"{errs} (l I issue, check {pv2})\n"
                        errmsgpv2 = f"{errs} (l I issue, check {pv1})\n"
                        self._checkDataMsg(
                            pv1=pv1, pv2=pv2, err1=errmsgpv1, err2=errmsgpv2
                        )
                    if re.search(regex, p1) and re.search(regex, p2):
                        if re.sub(regex, "@", p1) == re.sub(regex, "@", p2):
                            errmsgpv1 = f"{errs} (leading zero issue, check {pv2})\n"
                            errmsgpv2 = f"{errs} (leading zero issue, check {pv1})\n"
                            self._checkDataMsg(
                                pv1=pv1, pv2=pv2, err1=errmsgpv1, err2=errmsgpv2
                            )

            for prop in plist:
                errmsg = ""
                warnmsg = ""
                infomsg = ""
                pv = dev + ":" + prop
                if len(pv) > MAX_PV_LENGHT:
                    errmsg = f"Error: The PV is beyond {MAX_PV_LENGHT} characters\n"
                    self._checkDataMsg(pv1=pv, err1=errmsg)

                if len(prop) == 0:
                    errmsg = "Error: The PV Property is missing\n"
                    self._checkDataMsg(pv1=pv, err1=errmsg)

                if len(prop) > MAX_PROP_LENGHT:
                    errmsg = f"Error: The PV Property is beyond {MAX_PROP_LENGHT} characters ({len(prop)})\n"
                    if (TempErr[0] in prop) or (TempErr[1] in prop):
                        errmsg += tmperrmsg
                    self._checkDataMsg(pv1=pv, err1=errmsg)

                if prop.endswith("-S") or prop.endswith("_S"):
                    errmsg = "Error: The PV Property for a Setpoint value should end with -SP\n"
                    self._checkDataMsg(pv1=pv, err1=errmsg)

                if prop.endswith("-R") or prop.endswith("_R"):
                    errmsg = "Error: The PV Property for a Reading value should not contain any suffix\n"
                    self._checkDataMsg(pv1=pv, err1=errmsg)

                if prop.endswith("-RBV") or prop.endswith("_RBV"):
                    errmsg = "Error: The PV Property for a Readback value should end with -RB\n"
                    self._checkDataMsg(pv1=pv, err1=errmsg)

                if 0 < len(prop) < MAX_PROP_WARN:
                    warnmsg = f"Warning: The PV Property is below {MAX_PROP_WARN} characters ({len(prop)})\n"
                    self._checkDataMsg(pv1=pv, warn1=warnmsg)

                if any((c in self.charnotallow) for c in prop):
                    errmsg = (
                        "Error: The PV Property contains not allowed character(s)\n"
                    )
                    self._checkDataMsg(pv1=pv, err1=errmsg)

                if "#" in prop:
                    if prop.startswith("#"):
                        infomsg = 'Info: The PV is an "Internal PV"\n'
                        self._checkDataMsg(pv1=pv, info1=infomsg)
                    else:
                        errmsg = "Error: The PV Property contains the # character in not allowed position\n"
                        self._checkDataMsg(pv1=pv, err1=errmsg)

                if len(prop) > 0 and (
                    prop[0].isdigit()
                    or (prop[0] in self.charnotallow)
                    or (prop[0] == "_")
                    or (prop[0] == "-")
                ):
                    errmsg = "Error: The PV Property does not start alphabetical\n"
                    self._checkDataMsg(pv1=pv, err1=errmsg)
                if len(prop) > 0 and prop[0].islower():
                    warnmsg = "Warning: The PV Property does not start in upper case\n"
                    self._checkDataMsg(pv1=pv, warn1=warnmsg)

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

                if not (pv in self.PVWarnList or pv in self.PVErrList):
                    self.datainfo[pv] += "Info: The PV follows ESS PV Property Rules\n"

    def _checkValidName(self):
        """Check if the PV has a valid Name in the Naming Service"""
        for essname in self.PVDict.keys():
            s = essname.split(":")[0]

            try:
                sys, subsys = s.split("-")
            except Exception:
                sys = s
                subsys = ""

            if s not in self.SysStructCheckList.keys():
                self._checkSysStructName(sys, subsys)

            scheck = ""
            checkname = True
            nameok = False
            sname = ""
            if self.SysStructCheckList[sys] == self.notexist:
                scheck += (
                    f'Error: The System "{sys}" is not active in the Naming Service\n'
                )
                checkname = False

            if subsys != "" and self.SysStructCheckList[s] == self.notexist:
                scheck += f'Error: The Subsystem "{subsys}" of the System "{sys}" is not active in the Naming Service\n'
                checkname = False

            if not (essname.endswith(":")):
                dis, dev, idx = (essname.split(":")[1]).split("-")
                d = dis + "-" + dev
                if dev == "Virt":
                    scheck += f'Error: The Device "{dev}" of the Discipline "{dis}" is not valid\n'
                    checkname = False

                if d not in self.DevStructCheckList.keys():
                    self._checkDevStructName(dis, dev)

                if self.DevStructCheckList[dis] == self.notexist:
                    scheck += f'Error: The Discipline "{dis}" is not active in the Naming Service\n'
                    checkname = False

                if self.DevStructCheckList[d] == self.notexist:
                    scheck += f'Error: The Device "{dev}" of the Discipline "{dis}" is not active in the Naming Service\n'
                    checkname = False

                sname = essname
            else:
                sname = s

            if checkname:
                if sname not in self.EssNameCheckList.keys():
                    resp = self._getResp(self.urlname + sname)
                    try:
                        r = resp.json()
                        if r["status"] == "ACTIVE":
                            scheck += f'Info: The Name "{sname}" is registered in the Naming Service\n'
                            nameok = True
                        if r["status"] == "OBSOLETE":
                            scheck += f'Error: The Name "{sname}" was modified in the Naming Service\n'
                            nameok = False
                        if r["status"] == "DELETED":
                            scheck += f'Error: The Name "{sname}" was canceled in the Naming Service\n'
                            nameok = False

                    except Exception:
                        scheck += f'Error: The Name "{sname}" is not registered in the Naming Service\n'
                        nameok = False

            self.EssNameCheckList[sname] = nameok

            for prop in self.PVDict[essname]:
                pv = essname + ":" + prop
                if scheck not in self.datainfo[pv]:
                    self.datainfo[pv] += scheck
                if (not checkname) or (not self.EssNameCheckList[sname]):
                    self.VNameD[pv] = False
                else:
                    self.VNameD[pv] = True

    def _checkSysStructName(self, sys, subsys):
        """Check if the PV has a valid System and Subsystem part name"""
        resp = self._getResp(self.urlparts + sys)
        SysExist = 0
        SubsysExist = 0
        for item in resp.json():
            if (
                item["status"] == "Approved"
                and item["type"] == "System Structure"
                and (item["level"] == "2" or item["level"] == "1")
            ):
                SysExist = 1
                break

        if subsys != "":
            s = sys + "-" + subsys
            if SysExist:
                resp = self._getResp(self.urlparts + subsys)
                for item in resp.json():
                    if (
                        item["status"] == "Approved"
                        and item["type"] == "System Structure"
                        and item["level"] == "3"
                    ):
                        if s in item["mnemonicPath"]:
                            SubsysExist = 1
                            break
            self.SysStructCheckList[s] = SubsysExist

        self.SysStructCheckList[sys] = SysExist

    def _checkDevStructName(self, dis, dev):
        """Check if the PV has a valid Discipline part name"""
        resp = self._getResp(self.urlparts + dis)
        DisExist = 0
        DevExist = 0
        for item in resp.json():
            if (
                item["status"] == "Approved"
                and item["type"] == "Device Structure"
                and item["level"] == "1"
            ):
                DisExist = 1
                break
        d = dis + "-" + dev
        if DisExist:
            resp = self._getResp(self.urlparts + dev)
            for item in resp.json():
                if (
                    item["status"] == "Approved"
                    and item["type"] == "Device Structure"
                    and item["level"] == "3"
                ):
                    if d in item["mnemonicPath"]:
                        DevExist = 1
                        break

        self.DevStructCheckList[d] = DevExist
        self.DevStructCheckList[dis] = DisExist

    def _getPVFormat(self, pv):
        """If the PV has a valid format returns a list with each part name, otherwise and empty one"""
        try:
            s, d, prop = pv.split(":")
        except Exception:
            return []

        try:
            sys, sub = s.split("-")
        except Exception:
            sys = s
            sub = ""
        else:
            if sys == "" or sub == "":
                return []

        if d != "":
            try:
                dis, dev, idx = d.split("-")
                if dis == "" or dev == "":
                    return []
            except Exception:
                return []
        else:
            dis = ""
            dev = ""
            idx = ""

        return [sys, sub, dis, dev, idx, prop]

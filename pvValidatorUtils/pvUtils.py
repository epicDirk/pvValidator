import csv
import itertools
import re
import sys

if sys.version_info >= (3, 8, 0):
    from importlib.metadata import metadata
else:
    from email import message_from_string
    from pkg_resources import get_distribution

import requests

from . import epicsUtils, tabview


class pvUtils:
    def __init__(
        self, pvepics, namingservice, checkonlyfmt, pvfile, csvfile, epicsdb, stdout
    ):
        if sys.version_info >= (3, 8, 0):
            meta = metadata("pvValidatorUtils")
        else:
            dist = get_distribution("pvValidatorUtils")
            try:
                pkginfo = dist.get_metadata("METADATA")
            except FileNotFoundError:
                pkginfo = dist.get_metadata("PKG-INFO")
            meta = message_from_string(pkginfo)
        self.version = meta.get("Version")
        self.author = meta.get("Author")
        self.email = meta.get("Author-email")
        self.license = meta.get("License")
        self.platform = meta.get_all("Platform")
        self.epicsinfo = epicsUtils().getVersion
        self.pvepics = pvepics
        self.checkonlyfmt = checkonlyfmt
        self.pvfile = pvfile
        self.csvfile = csvfile
        self.epicsdb = epicsdb
        self.stdout = stdout
        self.exiterror = False
        url = None
        self.NS = None
        if namingservice == "test":
            url = "https://naming-test-01.cslab.esss.lu.se/"
            self.NS = "Testing"
        else:
            url = "https://naming.esss.lu.se/"
            self.NS = "Production"

        if pvfile is not None:
            with open(pvfile, "r") as pvf:
                Lines = pvf.readlines()
            for lin in Lines:
                if not lin.startswith("%") and not lin.startswith("#") and lin.strip():
                    self.pvepics.pvstringlist.push_back(lin.strip().split()[0])

        if epicsdb is not None:
            w = "record"
            listdb = []
            with open(epicsdb[0], "r") as fdb:
                for r in fdb:
                    if (
                        w in r
                        and not r.lstrip().startswith("#")
                        and not r.lstrip().startswith("f")
                        and not r.lstrip().startswith("i")
                    ):
                        listdb.append(
                            ((r.split(",")[1]).rsplit(")", 1)[0].strip()).strip('"')
                        )
            if len(epicsdb) > 1:
                with open(epicsdb[1]) as sub:
                    for s in sub:
                        if not s.startswith("%"):
                            try:
                                m, n = s.split()
                                listdb = [ll.replace(m, n) for ll in listdb]
                            except Exception:
                                pass
            if any("$" in string for string in listdb):
                if len(epicsdb) > 1:
                    print(
                        "It seems that you miss some macro substitution in the file %s for your EPICS DB %s, please check! Exit!"
                        % (epicsdb[1], epicsdb[0])
                    )
                else:
                    print(
                        "It seems that you miss some macro substitution file for your EPICS DB %s, please check! Exit!"
                        % epicsdb[0]
                    )
                sys.exit(1)

            for ldb in listdb:
                self.pvepics.pvstringlist.push_back(ldb)

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
        self.Title = "pvValidator %s" % self.version
        self.Widths = [6, 9, 10, 6, 6, 25, 60, 30]
        self.headers = {"accept": "application/json"}
        self.urlparts = url + "rest/parts/mnemonic/"
        self.urlname = url + "rest/deviceNames/"
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
        self.PVNotValid = 0
        self.PVRuleFail = 0
        self.PVInternal = 0
        self.PVRuleWarn = 0
        self.PVWrongFormat = 0
        self.PVNotRegistered = 0
        self.PVTot = len(self.pvepics.pvstringlist)
        self.charnotallow = set("!@$%^&*()+={}[]|\\:;'\"<>,.?/~`")

        if not checkonlyfmt:
            try:
                requests.head(url, timeout=1, verify=False)
            except requests.exceptions.ConnectionError as e:
                print(e)
                print("Fail to connect to Naming Service, exit!")
                sys.exit(1)

    def run(self):
        self.data.append(self.header)

        comm = None

        self._CheckValidFormat()
        self._CheckPropRules()
        if not self.checkonlyfmt:
            self._CheckValidName()

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
                _data += self._GetPVFormat(pv)

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
            Info = (
                "The PV list is taken from the server %s to perform online validation\n"
                % self.address
            )
        if self.pvfile is not None:
            Info = (
                "The PV list is taken from the file %s to perform offline validation\n"
                % self.pvfile
            )

        if self.epicsdb is not None:
            Info = (
                "The PV list is taken from the EPICS DB %s to perform offline validation\n"
                % self.epicsdb[0]
            )

        if self.checkonlyfmt:
            Info += "The Validation through Naming Service was skipped\n"
            Info += (
                "The Total PVs are = %i\nThe PVs with Wrong Format are = %i\nThe PVs with Rule Failure are = %i\nThe PVs with Rule Warning are = %i\nThe PVs Internal are = %i\n"
                % (
                    self.PVTot,
                    self.PVWrongFormat,
                    self.PVRuleFail,
                    self.PVRuleWarn,
                    self.PVInternal,
                )
            )
        else:
            Info += (
                "The Validation is done through " + self.NS + " Naming Service API\n"
            )
            Info += (
                "The Total PVs are = %i\nThe Total Not Valid PVs are = %i\nThe PVs with Wrong Format are = %i"
                "\nThe PVs with Rule Failure are = %i\nThe PVs with Rule Warning are = %i"
                "\nThe PVs with NOT Registered Name are = %i\nThe PVs Internal are = %i\n"
                % (
                    self.PVTot,
                    self.PVNotValid,
                    self.PVWrongFormat,
                    self.PVRuleFail,
                    self.PVRuleWarn,
                    self.PVNotRegistered,
                    self.PVInternal,
                )
            )

        i = self._GetDataInfo()
        Readme = "pvValidator %s\n" % self.version
        Readme += "Author: %s\n" % self.author
        Readme += "Author email: %s\n" % self.email
        Readme += "Platform: %s\n" % self.platform
        Readme += "%s\n" % self.epicsinfo
        Readme += 'pvValidator is an EPICS PV validation tool based on the "ESS Naming Convention" document (ESS-0000757)\n'
        Readme += (
            "pvValidator is realeased under the %s license (ESS - 2021)\n"
            % self.license
        )

        if self.csvfile is None and not self.stdout:
            tabview.view(
                self.data,
                info=Info,
                Title=self.Title,
                column_widths=self.Widths,
                datainfo=i,
                sumtitle=self.sumtitle,
                ioctitle=self.ioctitle,
                readme=Readme,
            )
        else:
            self.data[0].append(self.sumtitle)
            for j, d in enumerate(self.data):
                if j != 0:
                    self.data[j].append(i[d[6]])

            if self.stdout:
                for d in self.data:
                    print(" ".join(d))
                print(self.ioctitle)
                print(Info)
            else:
                self.data[0].append(self.ioctitle)
                self.data[1].append(Info)
                with open(self.csvfile, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerows(self.data)
        if self.exiterror:
            sys.exit(1)

    def _CheckValidFormat(self):
        for pv in self.pvlist:
            pvelem = self._GetPVFormat(pv)
            if self._IsValidFormat(pvelem, pv):
                self.VFormD[pv] = True
                dev, prop = pv.rsplit(":", 1)
                self.PVDict.setdefault(dev, []).append(prop)
            else:
                self.VFormD[pv] = False

    def _GetDataInfo(self):
        return self.datainfo

    def _IsValidFormat(self, pvelem, pv):
        if pvelem == []:
            self.datainfo[pv] = "Error: The PV does not follow any ESS Name Format\n"
            return False
        else:
            self.datainfo[pv] = "Info: The PV follows ESS Name Format\n"
            return True

    def _CheckDataMsg(self, **kwargs):
        pv1 = kwargs.get("pv1")
        err1 = kwargs.get("err1")
        warn1 = kwargs.get("warn1")
        info1 = kwargs.get("info1")
        pv2 = kwargs.get("pv2")
        err2 = kwargs.get("err2")

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

    def _CheckPropRules(self):
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
                    errmsgpv1 = "%s (duplication issue)\n" % (errs)
                    self._CheckDataMsg(pv1=pv1, err1=errmsgpv1)
                else:
                    if p1.lower() == p2.lower():
                        errmsgpv1 = "%s (case issue, check %s)\n" % (errs, pv2)
                        errmsgpv2 = "%s (case issue, check %s)\n" % (errs, pv1)
                        self._CheckDataMsg(
                            pv1=pv1, pv2=pv2, err1=errmsgpv1, err2=errmsgpv2
                        )
                    if p1 == p2.replace("O", "0") or p1 == p2.replace("0", "O"):
                        errmsgpv1 = "%s (0 O issue, check %s)\n" % (errs, pv2)
                        errmsgpv2 = "%s (0 O issue, check %s)\n" % (errs, pv1)
                        self._CheckDataMsg(
                            pv1=pv1, pv2=pv2, err1=errmsgpv1, err2=errmsgpv2
                        )
                    if p1 == p2.replace("VV", "W") or p1 == p2.replace("W", "VV"):
                        errmsgpv1 = "%s (VV W issue, check %s)\n" % (errs, pv2)
                        errmsgpv2 = "%s (VV W issue, check %s)\n" % (errs, pv1)
                        self._CheckDataMsg(
                            pv1=pv1, pv2=pv2, err1=errmsgpv1, err2=errmsgpv2
                        )
                    if p1 == p2.replace("1", "I") or p1 == p2.replace("I", "1"):
                        errmsgpv1 = "%s (1 I issue, check %s)\n" % (errs, pv2)
                        errmsgpv2 = "%s (1 I issue, check %s)\n" % (errs, pv1)
                        self._CheckDataMsg(
                            pv1=pv1, pv2=pv2, err1=errmsgpv1, err2=errmsgpv2
                        )
                    if p1 == p2.replace("1", "l") or p1 == p2.replace("l", "1"):
                        errmsgpv1 = "%s (1 l issue, check %s)\n" % (errs, pv2)
                        errmsgpv2 = "%s (1 l issue, check %s)\n" % (errs, pv1)
                        self._CheckDataMsg(
                            pv1=pv1, pv2=pv2, err1=errmsgpv1, err2=errmsgpv2
                        )
                    if p1 == p2.replace("I", "l") or p1 == p2.replace("l", "I"):
                        errmsgpv1 = "%s (l I issue, check %s)\n" % (errs, pv2)
                        errmsgpv2 = "%s (l I issue, check %s)\n" % (errs, pv1)
                        self._CheckDataMsg(
                            pv1=pv1, pv2=pv2, err1=errmsgpv1, err2=errmsgpv2
                        )
                    if re.search(regex, p1) and re.search(regex, p2):
                        if re.sub(regex, "@", p1) == re.sub(regex, "@", p2):
                            errmsgpv1 = "%s (leading zero issue, check %s)\n" % (
                                errs,
                                pv2,
                            )
                            errmsgpv2 = "%s (leading zero issue, check %s)\n" % (
                                errs,
                                pv1,
                            )
                            self._CheckDataMsg(
                                pv1=pv1, pv2=pv2, err1=errmsgpv1, err2=errmsgpv2
                            )

            for prop in plist:
                errmsg = ""
                warnmsg = ""
                infomsg = ""
                pv = dev + ":" + prop
                if len(pv) > 60:
                    errmsg = "Error: The PV is beyond 60 characters\n"
                    self._CheckDataMsg(pv1=pv, err1=errmsg)

                if len(prop) == 0:
                    errmsg = "Error: The PV Property is missing\n"
                    self._CheckDataMsg(pv1=pv, err1=errmsg)

                if len(prop) > 25:
                    errmsg = (
                        "Error: The PV Property is beyond 25 characters (%i)\n"
                        % len(prop)
                    )
                    if (TempErr[0] in prop) or (TempErr[1] in prop):
                        errmsg += tmperrmsg
                    self._CheckDataMsg(pv1=pv, err1=errmsg)

                if prop.endswith("-S") or prop.endswith("_S"):
                    errmsg = "Error: The PV Property for a Setpoint value should end with -SP\n"
                    self._CheckDataMsg(pv1=pv, err1=errmsg)

                if prop.endswith("-R") or prop.endswith("_R"):
                    errmsg = "Error: The PV Property for a Reading value should not contain any suffix\n"
                    self._CheckDataMsg(pv1=pv, err1=errmsg)

                if prop.endswith("-RBV") or prop.endswith("_RBV"):
                    errmsg = "Error: The PV Property for a Readback value should end with -RB\n"
                    self._CheckDataMsg(pv1=pv, err1=errmsg)

                if len(prop) > 1 and len(prop) < 4:
                    warnmsg = (
                        "Warning: The PV Property is below 4 characters (%i)\n"
                        % len(prop)
                    )
                    self._CheckDataMsg(pv1=pv, warn1=warnmsg)

                if any((c in self.charnotallow) for c in prop):
                    errmsg = (
                        "Error: The PV Property contains not allowed character(s)\n"
                    )
                    self._CheckDataMsg(pv1=pv, err1=errmsg)

                if "#" in prop:
                    if prop.startswith("#"):
                        infomsg = 'Info: The PV is an "Internal PV"\n'
                        self._CheckDataMsg(pv1=pv, info1=infomsg)
                    else:
                        errmsg = "Error: The PV Property contains the # character in not allowed position\n"
                        self._CheckDataMsg(pv1=pv, err1=errmsg)

                if len(prop) > 0 and (
                    prop[0].isdigit()
                    or (prop[0] in self.charnotallow)
                    or (prop[0] == "_")
                    or (prop[0] == "-")
                ):
                    errmsg = "Error: The PV Property does not start alphabetical\n"
                    self._CheckDataMsg(pv1=pv, err1=errmsg)
                if len(prop) > 0 and prop[0].islower():
                    warnmsg = "Warning: The PV Property does not start in upper case\n"
                    self._CheckDataMsg(pv1=pv, warn1=warnmsg)

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

    def _CheckValidName(self):
        for essname in self.PVDict.keys():
            s = essname.split(":")[0]

            try:
                sys, subsys = s.split("-")
            except Exception:
                sys = s
                subsys = ""

            if s not in self.SysStructCheckList.keys():
                self._CheckSysStructName(sys, subsys)

            scheck = ""
            checkname = True
            nameok = False
            sname = ""
            if self.SysStructCheckList[sys] == self.notexist:
                scheck += (
                    'Error: The System "%s" is not active in the Naming Service\n' % sys
                )
                checkname = False

            if subsys != "" and self.SysStructCheckList[s] == self.notexist:
                scheck += (
                    'Error: The Subsystem "%s" of the System "%s" is not active in the Naming Service\n'
                    % (subsys, sys)
                )
                checkname = False

            if not (essname.endswith(":")):
                dis, dev, idx = (essname.split(":")[1]).split("-")
                d = dis + "-" + dev
                if dev == "Virt":
                    scheck += (
                        'Error: The Device "%s" of the Discipline "%s" is not valid\n'
                        % (dev, dis)
                    )
                    checkname = False

                if d not in self.DevStructCheckList.keys():
                    self._CheckDevStructName(dis, dev)

                if self.DevStructCheckList[dis] == self.notexist:
                    scheck += (
                        'Error: The Discipline "%s" is not active in the Naming Service\n'
                        % dis
                    )
                    checkname = False

                if self.DevStructCheckList[d] == self.notexist:
                    scheck += (
                        'Error: The Device "%s" of the Discipline "%s" is not active in the Naming Service\n'
                        % (dev, dis)
                    )
                    checkname = False

                sname = essname
            else:
                sname = s

            if checkname:
                if sname not in self.EssNameCheckList.keys():
                    req = self.urlname + sname
                    resp = requests.get(req, headers=self.headers, verify=False)
                    try:
                        r = resp.json()
                        if r["status"] == "ACTIVE":
                            scheck += (
                                'Info: The Name "%s" is registered in the Naming Service\n'
                                % sname
                            )
                            nameok = True
                        if r["status"] == "OBSOLETE":
                            scheck += (
                                'Error: The Name "%s" was modified in the Naming Service\n'
                                % sname
                            )
                            nameok = False
                        if r["status"] == "DELETED":
                            scheck += (
                                'Error: The Name "%s" was canceled in the Naming Service\n'
                                % sname
                            )
                            nameok = False

                    except Exception:
                        scheck += (
                            'Error: The Name "%s" is not registered in the Naming Service\n'
                            % sname
                        )
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

    def _CheckSysStructName(self, sys, subsys):
        req = self.urlparts + sys
        resp = requests.get(req, headers=self.headers, verify=False)
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
                req = self.urlparts + subsys
                resp = requests.get(req, headers=self.headers, verify=False)
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

    def _CheckDevStructName(self, dis, dev):
        req = self.urlparts + dis
        resp = requests.get(req, headers=self.headers, verify=False)
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
            req = self.urlparts + dev
            resp = requests.get(req, headers=self.headers, verify=False)
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

    def _GetPVFormat(self, pv):
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

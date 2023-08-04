import csv
import itertools
import re
import sys
from email import message_from_string

import requests
from pkg_resources import get_distribution

from . import epicsUtils, tabview


class pvUtils:
    def __init__(
        self, pvepics, namingservice, checkonlyfmt, pvfile, csvfile, epicsdb, stdout
    ):
        self.version = get_distribution("pvValidatorUtils").version
        pkginfo = get_distribution("pvValidatorUtils").get_metadata("PKG-INFO")
        meta = message_from_string(pkginfo)
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
        if namingservice == "dev":
            url = "https://icsvd-app01.esss.lu.se:8443/names-test/"
            self.NS = "Development"
        elif namingservice == "stag":
            url = "https://icsvs-app01.esss.lu.se/naming/"
            self.NS = "Staging"
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
                requests.head(url, timeout=1)
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
        Readme += 'pvValidator is an EPICS PV validation tool based on the "ESS RULES FOR EPICS PV PROPERTY" document (ESS-3218463)\n'
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
            self.data[0].append(self.ioctitle)
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

    def _CheckDataInfo2(self, pv1, pv2, err1, err2):
        if err1 not in self.datainfo[pv1]:
            self.datainfo[pv1] += err1
        if err2 not in self.datainfo[pv2]:
            self.datainfo[pv2] += err2

    def _CheckDataInfo1(self, pv, msg):
        if msg not in self.datainfo[pv]:
            self.datainfo[pv] += msg

    def _CheckPropRules(self):
        PVErrList = []
        PVWarnList = []
        TempErr = ["-Drv01-SyncErr-Alrm", "-Enc01-LtchAutRstSp"]
        tmperrmsg = (
            "      !!!This issue should be fixed in version 8 of ECMCCFG Module!!!\n"
        )
        errs = "Error: The PV Property is not unique"
        regex = "0+(?![_A-Za-z-])(?!$)"
        for dev, plist in self.PVDict.items():
            for p1, p2 in itertools.combinations(plist, 2):
                pv1 = dev + ":" + p1
                pv2 = dev + ":" + p2
                dupl = False
                errmgspv1 = ""
                errmgspv2 = ""
                if p1 == p2:
                    self.datainfo[pv1] += "%s (duplication issue)\n" % (errs)
                    PVErrList.append(pv1)
                    dupl = True
                if (p1.lower() == p2.lower()) and not dupl:
                    e1 = "%s (case issue, check %s)\n" % (errs, pv2)
                    e2 = "%s (case issue, check %s)\n" % (errs, pv1)
                    self._CheckDataInfo2(pv1, pv2, e1, e2)
                    PVErrList.append(pv1)
                    PVErrList.append(pv2)
                if (
                    p1 == p2.replace("O", "0") or p1 == p2.replace("0", "O")
                ) and not dupl:
                    errmgspv1 = "%s (0 O issue, check %s)\n" % (errs, pv2)
                    errmgspv2 = "%s (0 O issue, check %s)\n" % (errs, pv1)
                    self._CheckDataInfo2(pv1, pv2, errmgspv1, errmgspv2)
                    PVErrList.append(pv1)
                    PVErrList.append(pv2)
                if (
                    p1 == p2.replace("VV", "W") or p1 == p2.replace("W", "VV")
                ) and not dupl:
                    errmgspv1 = "%s (VV W issue, check %s)\n" % (errs, pv2)
                    errmgspv2 = "%s (VV W issue, check %s)\n" % (errs, pv1)
                    self._CheckDataInfo2(pv1, pv2, errmgspv1, errmgspv2)
                    PVErrList.append(pv1)
                    PVErrList.append(pv2)
                if (
                    p1 == p2.replace("1", "I") or p1 == p2.replace("I", "1")
                ) and not dupl:
                    errmgspv1 = "%s (1 I issue, check %s)\n" % (errs, pv2)
                    errmgspv2 = "%s (1 I issue, check %s)\n" % (errs, pv1)
                    self._CheckDataInfo2(pv1, pv2, errmgspv1, errmgspv2)
                    PVErrList.append(pv1)
                    PVErrList.append(pv2)

                if (
                    p1 == p2.replace("1", "l") or p1 == p2.replace("l", "1")
                ) and not dupl:
                    errmgspv1 = "%s (1 l issue, check %s)\n" % (errs, pv2)
                    errmgspv2 = "%s (1 l issue, check %s)\n" % (errs, pv1)
                    self._CheckDataInfo2(pv1, pv2, errmgspv1, errmgspv2)
                    PVErrList.append(pv1)
                    PVErrList.append(pv2)

                if (
                    p1 == p2.replace("I", "l") or p1 == p2.replace("l", "I")
                ) and not dupl:
                    errmgspv1 = "%s (l I issue, check %s)\n" % (errs, pv2)
                    errmgspv2 = "%s (l I issue, check %s)\n" % (errs, pv1)
                    self._CheckDataInfo2(pv1, pv2, errmgspv1, errmgspv2)
                    PVErrList.append(pv1)
                    PVErrList.append(pv2)

                if (re.search(regex, p1) and re.search(regex, p2)) and not dupl:
                    if re.sub(regex, "@", p1) == re.sub(regex, "@", p2):
                        errmgspv1 = "%s (leading zero issue, check %s)\n" % (errs, pv2)
                        errmgspv2 = "%s (leading zero issue, check %s)\n" % (errs, pv1)
                        self._CheckDataInfo2(pv1, pv2, errmgspv1, errmgspv2)
                        PVErrList.append(pv1)
                        PVErrList.append(pv2)

            for prop in plist:
                errmsg = ""
                warnmsg = ""
                infomsg = ""
                pv = dev + ":" + prop
                if len(pv) > 60:
                    errmsg = "Error: The PV is beyond 60 characters\n"
                    self._CheckDataInfo1(pv, errmsg)
                    PVErrList.append(pv)

                if len(prop) == 0:
                    errmsg = "Error: The PV Property is missing\n"
                    self._CheckDataInfo1(pv, errmsg)
                    PVErrList.append(pv)

                if len(prop) > 25:
                    errmsg = (
                        "Error: The PV Property is beyond 25 characters (%i)\n"
                        % len(prop)
                    )
                    self._CheckDataInfo1(pv, errmsg)
                    if (TempErr[0] in prop) or (TempErr[1] in prop):
                        self._CheckDataInfo1(pv, tmperrmsg)
                    PVErrList.append(pv)

                elif len(prop) > 20:
                    if not (
                        (prop.endswith("-R") or prop.endswith("-S")) and len(prop) <= 22
                    ) and not ((prop.endswith("-RB")) and len(prop) <= 23):
                        warnmsg = (
                            "Warning: The PV Property is beyond 20 characters (%i)\n"
                            % len(prop)
                        )
                        self._CheckDataInfo1(pv, warnmsg)
                        PVWarnList.append(pv)
                if len(prop) > 1 and len(prop) < 4 and prop != "Pwr":
                    warnmsg = (
                        "Warning: The PV Property is below 4 characters (%i)\n"
                        % len(prop)
                    )
                    self._CheckDataInfo1(pv, warnmsg)
                    PVWarnList.append(pv)

                if any((c in self.charnotallow) for c in prop):
                    errmsg = (
                        "Error: The PV Property contains not allowed character(s)\n"
                    )
                    self._CheckDataInfo1(pv, errmsg)
                    PVErrList.append(pv)

                if "#" in prop:
                    if prop.startswith("#"):
                        infomsg = 'Info: The PV is an "Internal PV"\n'
                        self._CheckDataInfo1(pv, infomsg)
                        self.PVInternal += 1
                    else:
                        errmsg = "Error: The PV Property contains the # character in not allowed position\n"
                        self._CheckDataInfo1(pv, errmsg)
                        PVErrList.append(pv)

                if len(prop) > 0 and (
                    prop[0].isdigit()
                    or (prop[0] in self.charnotallow)
                    or (prop[0] == "_")
                    or (prop[0] == "-")
                ):
                    errmsg = "Error: The PV Property does not start alphabetical\n"
                    self._CheckDataInfo1(pv, errmsg)
                    PVErrList.append(pv)
                if len(prop) > 0 and prop[0].islower():
                    warnmsg = "Warning: The PV Property does not start in upper case\n"
                    self._CheckDataInfo1(pv, warnmsg)
                    PVWarnList.append(pv)

        for dev, plist in self.PVDict.items():
            for prop in plist:
                pv = dev + ":" + prop

                if pv in PVErrList:
                    self.VRuleD[pv] = False
                    self.VWarnD[pv] = False
                elif pv in PVWarnList:
                    self.VRuleD[pv] = False
                    self.VWarnD[pv] = True
                else:
                    self.VWarnD[pv] = False
                    self.VRuleD[pv] = True

                if not (pv in PVWarnList or pv in PVErrList):
                    self.datainfo[pv] += "Info: The PV follows ESS PV Property Rules\n"

    # def _HasAlias(self,pv):
    #    print (self.pvepics.HasAlias(pv))

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
                    'Error: the System "%s" does not exist in the Naming Service\n'
                    % sys
                )
                checkname = False

            if subsys != "" and self.SysStructCheckList[s] == self.notexist:
                scheck += (
                    'Error: the Subsystem "%s" of the System "%s" does not exist in the Naming Service\n'
                    % (subsys, sys)
                )
                checkname = False

            if not (essname.endswith(":")):
                dis, dev, idx = (essname.split(":")[1]).split("-")
                d = dis + "-" + dev
                if d not in self.DevStructCheckList.keys():
                    self._CheckDevStructName(dis, dev)

                if self.DevStructCheckList[dis] == self.notexist:
                    scheck += (
                        'Error: the Discipline "%s" does not exist in the Naming Service\n'
                        % dis
                    )
                    checkname = False

                if self.DevStructCheckList[d] == self.notexist:
                    scheck += (
                        'Error: the Device "%s" of the Discipline "%s" does not exist in the Naming Service\n'
                        % (dev, dis)
                    )
                    checkname = False

                sname = essname
            else:
                sname = s

            if checkname:
                if sname not in self.EssNameCheckList.keys():
                    req = self.urlname + sname
                    resp = requests.get(req, headers=self.headers)
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
        resp = requests.get(req, headers=self.headers)
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
                resp = requests.get(req, headers=self.headers)
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
        resp = requests.get(req, headers=self.headers)
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
            resp = requests.get(req, headers=self.headers)
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

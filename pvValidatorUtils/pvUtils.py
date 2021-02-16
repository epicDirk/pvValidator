import sys
import requests
from . import tabview
from . import epicsUtils
import itertools
from pkg_resources import get_distribution
from email import message_from_string
import csv

class pvUtils:
    def __init__(self,pvepics,checkonlyfmt,pvfile,csvfile):
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
        if (pvfile is not None):
            with open(pvfile,'r') as pvf:
                Lines = pvf.readlines()
            for lin in Lines:
                self.pvepics.pvstringlist.push_back(lin.strip())
        
        self.pvlist = self.pvepics.pvstringlist
        self.address = self.pvepics.getAddress
        self.header = ["System","Subsystem","Discipline","Device","Index","Property","PV Name","Validation Comment"]
        self.sumtitle = "PV Summary"
        self.ioctitle = "Validation Summary"
        self.data = []
        self.Title = "pvValidator %s" % self.version
        self.Widths = [6,9,10,6,6,25,60,30]
        self.headers = {'accept': 'application/json'}
        self.urlparts = "https://naming.esss.lu.se/rest/parts/mnemonic/"
        self.urlname = "https://naming.esss.lu.se/rest/deviceNames/"
        self.exist = 1
        self.notexist = 0
        self.empty = 2
        self.datainfo = {}
        self.PVDict = {}
        self.VFormD = {}
        self.VRuleD = {}
        self.VNameD = {}
        self.PVNotValid = 0
        self.PVRuleFail = 0
        self.PVInternal = 0
        self.PVTot = len(self.pvepics.pvstringlist)
        self.charnotallow = set("!@$%^&*()+={}[]|\\:;'\"<>,.?/~`")

        if ( not checkonlyfmt):
            try:
                requests.head("https://naming.esss.lu.se",timeout=1)
            except requests.exceptions.ConnectionError as e:
                print (e)
                print ("Fail to connect to Naming Service, exit!")
                sys.exit(1)

    def run(self):
        self.data.append(self.header)
        
        comm = None         
        
        self._CheckValidFormat()
        self._CheckPropRules()
        if ( not self.checkonlyfmt):
            self._CheckValidName()
        
        
     
        for pv in self.pvlist:
            _data = []
            
            

            if ( not self.VFormD[pv]) or ((not self.checkonlyfmt) and (  not self.VNameD[pv]) ):
                _data += ["------" for _ in range(6)]
            elif (self.VFormD[pv] and (self.checkonlyfmt)):
                _data += ["******" for _ in range(6)]
                self.datainfo[pv] += "Info: Skip Validation Check with Naming API"
            else:
                _data += self._GetPVFormat(pv)


            if ( not self.VFormD[pv]):
                comm = "NOT VALID (Wrong Format)"
                self.PVNotValid +=1
            elif ( self.VFormD[pv] and (not self.VRuleD[pv]) and self.checkonlyfmt):
                comm = "OK Format, Rule Fail"
                self.PVRuleFail +=1
            elif ( self.VFormD[pv] and self.VRuleD[pv] and self.checkonlyfmt):
                comm = "OK Format, OK Rule"
            elif ( self.VFormD[pv] and self.VRuleD[pv] and ((not self.checkonlyfmt) and self.VNameD[pv])):
                comm = "VALID"
            elif ( self.VFormD[pv] and self.VRuleD[pv] and ((not self.checkonlyfmt) and (not self.VNameD[pv]))):
                comm = "NOT VALID (Name Fail)"
                self.PVNotValid +=1
            elif (self.VFormD[pv] and (not self.VRuleD[pv]) and ((not self.checkonlyfmt) and self.VNameD[pv] ) ):
                comm = "NOT VALID (Rule Fail)"
                self.PVNotValid +=1
            elif (self.VFormD[pv] and (not self.VRuleD[pv]) and ((not self.checkonlyfmt) and (not self.VNameD[pv]) ) ):
                comm = "NOT VALID (Name and Rule Fail)"
                self.PVNotValid +=1
                

            _data.append(pv)
            _data.append(comm)    
            self.data.append(_data)
        
        if (self.address):
            Info = "The PV list is taken from the server %s to perform online validation\n" % self.address
        if (self.pvfile is not None):
            Info = "The PV list is taken from the file %s to perform offline validation\n" %self.pvfile

        if (self.checkonlyfmt):
            Info += "The Validation through Naming Service was skipped\n"
            Info += "The Total PVs are = %i\nThe PVs Not Valid are = %i (wrong format)\nThe PVs Rule Fail are = %i\nThe PVs Internal are = %i\n" %( self.PVTot,self.PVNotValid,self.PVRuleFail,self.PVInternal )
        else:
            Info += "The Total PVs are = %i\nThe PVs Not Valid are = %i\nThe PVs Internal are = %i\n" %( self.PVTot,self.PVNotValid,self.PVInternal )
        
        i = self._GetDataInfo()
        Readme = "pvValidator %s\n" % self.version
        Readme += "Author: %s\n" % self.author
        Readme += "Author email: %s\n" % self.email
        Readme += "Platform: %s\n" % self.platform
        Readme += "%s\n" % self.epicsinfo
        Readme += "pvValidator is an EPICS PV validation tool based on the \"ESS RULES FOR EPICS PV PROPERTY\" document (ESS-XXXXXXX)\n"
        Readme += "pvValidator is realeased under the %s license (ESS - 2021)\n" %self.license
        
        if (self.csvfile is None):
            tabview.view(self.data,info=Info,Title=self.Title,column_widths=self.Widths,datainfo=i,sumtitle=self.sumtitle,ioctitle=self.ioctitle,readme=Readme)
        else:
            self.data[0].append(self.sumtitle)
            self.data[0].append(self.ioctitle)
            for j,d in enumerate(self.data):
                
                if j !=0:
                    self.data[j].append(i[d[6]])

            self.data[1].append(self.Info)
            

            
            
        
            with open(self.csvfile, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(self.data)

    def _CheckValidFormat(self):
        for pv in self.pvlist:
            
            pvelem = self._GetPVFormat(pv)
            if self._IsValidFormat(pvelem,pv):
                self.VFormD[pv]=True
                dev,prop = pv.rsplit(":",1)
                self.PVDict.setdefault(dev,[]).append(prop)
            else:
                self.VFormD[pv]=False

        

    def _GetDataInfo(self):
        return self.datainfo

    def _IsValidFormat(self,pvelem,pv):
        if pvelem == []:
            self.datainfo[pv] = "Error: The PV does not follow any ESS Name Format\n"
            return False
        else:
            self.datainfo[pv] = "Info: The PV follows ESS Name Format\n" 
            return True
    
    def _CheckPropRules(self):
        PVErrList = []
        PVWarnList = []
        errs = "Error: The PV Property is not unique" 
        for dev,plist in self.PVDict.items():
            for p1,p2 in itertools.combinations(plist, 2):
                pv1 = dev+":"+p1
                pv2 = dev+":"+p2
                if p1.lower() == p2.lower():
                    self.datainfo[pv1] += "%s (case issue, check %s)\n" % (errs,pv2)
                    self.datainfo[pv2] += "%s (case issue, check %s)\n" % (errs,pv1)
                    PVErrList.append(pv1)
                    PVErrList.append(pv2)
                if p1 == p2.replace("O","0") or p1== p2.replace("0","O"):
                    self.datainfo[pv1] += "%s (0 O issue, check %s)\n" % (errs,pv2)
                    self.datainfo[pv2] += "%s (0 O issue, check %s)\n" % (errs,pv1)
                    PVErrList.append(pv1)
                    PVErrList.append(pv2)
                if p1 == p2.replace("VV","W") or p1== p2.replace("W","VV"):
                    self.datainfo[pv1] += "%s (VV W issue, check %s)\n" % (errs,pv2)
                    self.datainfo[pv2] += "%s (VV W issue, check %s)\n" % (errs,pv1)
                    PVErrList.append(pv1)
                    PVErrList.append(pv2)
                if p1 == p2.replace("1","I") or p1== p2.replace("I","1"):
                    self.datainfo[pv1] += "%s (1 I issue, check %s)\n" % (errs,pv2)
                    self.datainfo[pv2] += "%s (1 I issue, check %s)\n" % (errs,pv1)
                    PVErrList.append(pv1)
                    PVErrList.append(pv2)
                
                if p1 == p2.replace("1","l") or p1== p2.replace("l","1"):
                    self.datainfo[pv1] += "%s (1 l issue, check %s)\n" % (errs,pv2)
                    self.datainfo[pv2] += "%s (1 l issue, check %s)\n" % (errs,pv1)
                    PVErrList.append(pv1)
                    PVErrList.append(pv2)

                if p1 == p2.replace("I","l") or p1== p2.replace("l","I"):
                    self.datainfo[pv1] += "%s (l I issue, check %s)\n" % (errs,pv2)
                    self.datainfo[pv2] += "%s (l I issue, check %s)\n" % (errs,pv1)
                    PVErrList.append(pv1)
                    PVErrList.append(pv2)

                if (p1.find("0") ==  p2.find("0")) and (p1.find("0") !=-1):
                    if (p1.endswith("0") and p2.endswith("0")) or (not p1.endswith("0") and not p2.endswith("0")):
                        if p1.replace("0","") == p2.replace("0",""):
                            self.datainfo[pv1] += "%s (leading zero issue, check %s)\n" % (errs,pv2)
                            self.datainfo[pv2] += "%s (leading zero issue, check %s)\n" % (errs,pv1)
                            PVErrList.append(pv1)
                            PVErrList.append(pv2)
 
                

            for prop in plist:
                
                
                pv = dev+":"+prop
                if len(pv) > 60:
                    self.datainfo[pv] += "Error: The PV is beyond 60 characters\n" 
                    PVErrList.append(pv)

                if len(prop) > 25:
                    self.datainfo[pv] += "Error: The PV Property is beyond 25 characters\n" 
                    PVErrList.append(pv)

                elif len(prop) > 20:
                    if  not ((prop.endswith("-R") or prop.endswith("-S") ) and len(prop) <= 22) and not ((prop.endswith("-RB")) and len(prop) <=23):
                        self.datainfo[pv] +=  "Warning: The PV Property is beyond 20 characters (%i)\n" % len(prop)
                        PVWarnList.append(pv)
                if len(prop) < 4:
                    self.datainfo[pv] +=  "Warning: The PV Property is below 4 characters (%i)\n" % len(prop) 
                    PVWarnList.append(pv)
        
            
                if any((c in self.charnotallow) for c in prop):
                    self.datainfo[pv] += "Error: The PV Property contains not allowed character(s)\n"
                    PVErrList.append(pv)

                if "#" in prop:
                    if prop.startswith('#'):
                        self.datainfo[pv] += "Info: The PV is an \"Internal PV\"\n"
                        self.PVInternal +=1
                    else:
                        self.datainfo[pv] += "Error: The PV Property contains the # character in not allowed position\n" 
                        PVErrList.append(pv)
        
                if prop[0].isdigit() or (prop[0] in self.charnotallow) or (prop[0] == "_") or (prop[0]=="-"):
                    self.datainfo[pv] += "Error: The PV Property does not start alphabetical\n"
                    PVErrList.append(pv)
                if prop[0].islower():
                    self.datainfo[pv] += "Warning: The PV Property does nost start in upper case\n"
                    PVWarnList.append(pv)
        
        
        for dev,plist in self.PVDict.items():
            for prop in plist:
                pv = dev+":"+prop

                if (pv in PVErrList):
                    #self.datainfo[pv] += "Info: The PV does not follow some ESS PV Property Rules\n"
                    self.VRuleD[pv]=False
                else:
                    self.VRuleD[pv]=True

                #if (pv in PVWarnList and pv not in PVErrList):
                #    self.datainfo[pv] += "Info: The PV follows ESS PV Property Rules with some Warnings\n"
                    

                if not (pv in PVWarnList or pv in PVErrList):
                    self.datainfo[pv] += "Info: The PV follows ESS PV Property Rules\n" 
        
        

        
    #def _HasAlias(self,pv):
    #    print (self.pvepics.HasAlias(pv))
        
    def _CheckValidName(self):
        for essname in self.PVDict.keys():
            s = essname.split(":")[0]
                
            try:
                sys,subsys = s.split("-")
                #syscheck,subsyscheck=0,0 #TEMP
            except Exception:
                sys=s
                subsys = ""
                #syscheck,subsyscheck=0,2 #TEMP

            syscheck,subsyscheck=self._CheckSysStructName(sys,subsys)
            
            
            
            if not (essname.endswith(":")):
                dis,dev,idx = (essname.split(":")[1]).split("-")
                discheck,devcheck = self._CheckDevStructName(dis,dev)
                #discheck,devcheck=0,0 #TEMP
            else:
                discheck,devcheck = self.empty,self.empty
           
                          
                        
            


            scheck = ""
            checkname = True
            nameok = False
            if (syscheck==self.notexist):
                scheck += "Error: the System \"%s\" does not exist in the Naming Service\n" % sys
                checkname = False

            if (subsyscheck==self.notexist):
                scheck += "Error: the Subsystem \"%s\" does not exist in the Naming Service\n" % subsys
                checkname = False
            
            if (discheck==self.notexist):
                scheck += "Error: the Discipline \"%s\" does not exist in the Naming Service\n" % dis
                checkname = False
            
            if (devcheck==self.notexist):
                scheck += "Error: the Device \"%s\" does not exist in the Naming Service\n" % dev
                checkname = False

            if (checkname):
                if essname.endswith(":"):
                    sname = essname.split(":")[0]
                else:
                    sname = essname
                req = self.urlname+sname
                resp = requests.get(req,headers=self.headers)
                try:
                    r = resp.json()
                    if r['status'] == "ACTIVE":
                        scheck +="Info: The Name \"%s\" is registered in the Naming Service\n" % sname
                        nameok = True
                except Exception:
                    scheck+="Error: The Name \"%s\" is not registered in the Naming Service\n" % sname
                    nameok = False
            

        
            for prop in self.PVDict[essname]:
                pv = essname+":"+prop
                self.datainfo[pv] += scheck
                if (not checkname) or ( not nameok ):
                    self.VNameD[pv] = False
                else:
                    self.VNameD[pv] = True
                
        


    
    def _CheckSysStructName(self,sys,subsys):
        req = self.urlparts+sys
        resp = requests.get(req,headers=self.headers)
        #r = resp.json()
        SysExist = 0
        struct = "System Structure"
        for item in resp.json():
            if item['status']  == "Approved" and item['type']==struct and (item['level']=="2" or item['level'] =="1"):
                SysExist = 1
                break
        
        if subsys !="":
            req = self.urlparts+subsys
            resp = requests.get(req,headers=self.headers)
            #r = resp.json()
            SubsysExist = 0
            for item in resp.json():
                if item['status'] == "Approved" and item['type']==struct and item['level']=="3":
                    if sys+"-"+subsys in item['mnemonicPath']:
                        SubsysExist = 1
                        break
            return SysExist,SubsysExist
        else:
            return SysExist,2
        
    def _CheckDevStructName(self,dis,dev):
        if dis =="":
            return 2,2
        req = self.urlparts+dis
        resp = requests.get(req,headers=self.headers)
        #r = resp.json()
        DisExist = 0
        struct = "Device Structure"
        for item in resp.json():
            if item['status']  == "Approved" and item['type']==struct and item['level']=="1":
                DisExist = 1
                break
        req = self.urlparts+dev
        resp = requests.get(req,headers=self.headers)
        #r = resp.json()
        DevExist = 0
        for item in resp.json():
            if item['status']  == "Approved" and item['type']==struct and item['level']=="3":
                DevExist = 1
                break
        return DisExist,DevExist

    
        



    def _GetPVFormat(self,pv):
        try:
            s,d,prop = pv.split(':')
        except Exception:
            return []

        try:
            sys,sub=s.split('-')
        except Exception:
            sys = s
            sub = ""
        else:
            if sys == "" or sub =="":
                return []

        if d != "":
            try:
                dis,dev,idx=d.split('-')
            except Exception:
                return []
        else:
            dis=""
            dev=""
            idx=""

    
        return [sys,sub,dis,dev,idx,prop]
        



  



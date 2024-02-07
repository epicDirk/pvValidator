import tempfile
from os import environ
from time import sleep

import pytest
from run_iocsh import IOC

from pvValidatorUtils import epicsUtils, pvUtils

fmtfile = "test/pvlist_fmt.txt"
rulefile = "test/pvlist_rule.txt"
apifile = "test/pvlist_api.txt"
okfile = "test/pvlist_ok.txt"
epicsdbfile = ["test/test.db", "test/test.macro"]
tmpf = tempfile.NamedTemporaryFile(suffix=".csv")


@pytest.fixture
def pvobj_pvfmt():
    pvepics = epicsUtils(False)
    return pvUtils(pvepics, "prod", True, fmtfile, None, None, True)


@pytest.fixture
def pvobj_pvcheck():
    pvepics = epicsUtils(False)
    return pvUtils(pvepics, "prod", True, rulefile, None, None, True)


@pytest.fixture
def pvobj_pvdb():
    pvepics = epicsUtils(False)
    return pvUtils(pvepics, "prod", True, None, None, epicsdbfile, True)


@pytest.fixture
def pvobj_fromioc():
    env_vars = ["EPICS_BASE", "E3_REQUIRE_VERSION"]
    base, require = map(environ.get, env_vars)
    assert base, "source your EPICS Emv"
    assert require, "source your EPICS Env"
    environ["IOCNAME"] = "Sys-Sub:SC-IOC-001"
    args = ["test/test.db", "P=Sys-Sub:", "R=Dis-Dev-Idx:"]
    ioc = IOC(*args, ioc_executable="iocsh", timeout=20.0)
    ioc.start()
    assert ioc.is_running()
    sleep(1)
    pvepics = epicsUtils("localhost")
    return pvUtils(pvepics, "prod", True, None, None, None, True)


@pytest.fixture
def pvobj_backend():
    pvepics = epicsUtils(False)
    return pvUtils(pvepics, "prod", False, apifile, None, None, True)


@pytest.fixture
def pvobj_all():
    pvepics = epicsUtils(False)
    return pvUtils(pvepics, "prod", False, okfile, tmpf.name, None, False)


def test_pvformat(pvobj_pvfmt: pvUtils):
    with open(fmtfile, "r") as fp:
        lines = sum(not line.isspace() and not line.startswith("%") for line in fp)
    pvlist = pvobj_pvfmt.pvepics.pvstringlist
    assert pvlist.size() == lines, "Wrong PV list size extracted from input text file!"
    pvobj_pvfmt._CheckValidFormat()
    assert len(pvobj_pvfmt.VFormD) == lines, "Wrong PV format dictionary size!"
    for pv in pvlist:
        print(pv)
        assert not pvobj_pvfmt.VFormD[pv], "Wrong PV format not identified!"


def test_pvprop(pvobj_pvcheck: pvUtils):
    with open(rulefile, "r") as fp:
        lines = sum(not line.isspace() and not line.startswith("%") for line in fp)
    pvlist = pvobj_pvcheck.pvepics.pvstringlist
    assert pvlist.size() == lines, "Wrong PV list size extracted from input text file!"
    pvobj_pvcheck._CheckValidFormat()
    pvobj_pvcheck._CheckPropRules()
    for c, pv in enumerate(pvlist):
        print(pv)
        if c > 18:
            assert not pvobj_pvcheck.VWarnD[pv], "PV rule warning not identified!"
        else:
            assert not pvobj_pvcheck.VRuleD[pv], "PV rule failure not identified!"
    assert pvobj_pvcheck.PVInternal == 2, "PV internal wrongly counted!"


def test_epicsdb(pvobj_pvdb: pvUtils):
    pvlist = pvobj_pvdb.pvepics.pvstringlist
    assert pvlist.size() == 3, "Wrong PV list size extracted from EPICS Db file!"
    PVToReadFromDB = [
        "Sys-Sub:Dis-Dev-Idx:MyAnalogVar",
        "Sys-Sub:Dis-Dev-Idx:MyBoolVar",
        "Sys-Sub:Dis-Dev-Idx:MyWaveVar",
    ]
    for i in range(pvlist.size()):
        assert (
            pvlist[i] == PVToReadFromDB[i]
        ), "Wrong PV name extracted from EPICS Db file!"


def test_pvfromioc(pvobj_fromioc: pvUtils):
    pvlist = pvobj_fromioc.pvepics.pvstringlist
    assert pvlist.size() == 8, "Wrong PV list from IOC"


def test_backend(pvobj_backend: pvUtils):
    with open(apifile, "r") as fp:
        lines = sum(not line.isspace() and not line.startswith("%") for line in fp)
    pvlist = pvobj_backend.pvepics.pvstringlist
    assert pvlist.size() == lines, "Wrong PV list size extracted from input text file!"
    pvobj_backend._CheckValidFormat()
    pvobj_backend._CheckPropRules()
    pvobj_backend._CheckValidName()
    assert len(pvobj_backend.VNameD) == lines, "Wrong PV Name dictionary size!"
    for pv in pvlist:
        print(pv)
        assert not pvobj_backend.VNameD[pv], "Not registered ESS Name not identified!"


def test_all(pvobj_all: pvUtils):
    pvobj_all.run()
    w = b"The PVs with Rule Failure are = 0"
    c = tmpf.read()
    assert w in c, "Wrong csv file created!"
    with open(okfile, "r") as fp:
        lines = sum(not line.isspace() and not line.startswith("%") for line in fp)
    pvlist = pvobj_all.pvepics.pvstringlist
    assert pvlist.size() == lines, "Wrong PV list size extracted from input text file!"
    assert len(pvobj_all.VNameD) == lines, "Wrong PV Name dictionary size!"
    for pv in pvlist:
        print(pv)
        assert pvobj_all.VNameD[pv], "Wrong PV validation!"

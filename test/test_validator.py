import pathlib
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
epicsdbfile = ["test/test.db", "P=Sys-Sub:,R=Dis-Dev-Idx:"]
subsfile = ["test/test.substitutions", "PP=Sys-Sub:,RR=Dis-Dev-Idx:"]
tmpf1 = tempfile.NamedTemporaryFile(suffix=".csv")


@pytest.fixture
def pvobj_pvfmt():
    """This fixture is to check the PV format
    The PV list is given from the text file fmtfile
    """
    pvepics = epicsUtils()
    return pvUtils(pvepics=pvepics, checkonlyfmt=True, pvfile=fmtfile, stdout=True)


@pytest.fixture
def pvobj_pvcheck():
    """This fixture is to check the PV property rules
    The PV list is given from the text file rulefile
    """
    pvepics = epicsUtils()
    return pvUtils(pvepics=pvepics, checkonlyfmt=True, pvfile=rulefile, stdout=True)


@pytest.fixture
def pvobj_pvdb():
    """This fixture is to check the parsing of an EPICS database to get the PV list
    The PV list is given from the epics database file epicsdbfile
    """
    pvepics = epicsUtils()
    return pvUtils(pvepics=pvepics, checkonlyfmt=True, epicsdb=epicsdbfile, stdout=True)


@pytest.fixture
def pvobj_pvsubs():
    """This fixture is to check the creation (via msi code) and parsing of an EPICS database to the PV list
    The PV list is given from the substitution file subsfile
    """
    pvepics = epicsUtils()
    return pvUtils(pvepics, checkonlyfmt=True, msiobj=subsfile, stdout=True)


@pytest.fixture
def pvobj_fromioc():
    """This fixture is to check the PV fetching from an IOC"""
    requirepath = environ.get("E3_REQUIRE_LOCATION")
    assert requirepath, "Source your EPICS Env"
    environ["IOCNAME"] = "Sys-Sub:SC-IOC-001"
    test_cmd = pathlib.Path(__file__).parent / "test.cmd"
    ioc = IOC(test_cmd, timeout=20.0)
    ioc.start()
    sleep(1)
    pvepics = epicsUtils("localhost")
    return pvUtils(pvepics=pvepics, checkonlyfmt=True, stdout=True)


@pytest.fixture
def pvobj_backend():
    """This fixture is to check the naming service api
    The PV list is given from the text file apifile
    """
    pvepics = epicsUtils()
    return pvUtils(pvepics=pvepics, pvfile=apifile, stdout=True)


@pytest.fixture
def pvobj_all():
    """
    This fixture is to check the entire PV validation sequence
    The PV list is given from the text file okfile
    The PV validation outcome is written in the temporary file tmpf1.name
    """
    pvepics = epicsUtils()
    return pvUtils(pvepics=pvepics, pvfile=okfile, csvfile=tmpf1.name)


def get_lines(file):
    """Give the total numner of PV counting them from the input text file"""
    return sum(
        not line.isspace() and not line.startswith("%")
        for line in pathlib.Path(file).open()
    )


def test_pvformat(pvobj_pvfmt: pvUtils):
    """Testing the reading of the text file and PV format"""
    lines = get_lines(fmtfile)
    pvlist = pvobj_pvfmt.pvepics.pvstringlist
    assert pvlist.size() == lines, "Wrong PV list size extracted from input text file!"
    pvobj_pvfmt._checkValidFormat()
    assert len(pvobj_pvfmt.VFormD) == lines, "Wrong PV format dictionary size!"
    for pv in pvlist:
        assert not pvobj_pvfmt.VFormD[pv], (
            "Wrong format of PV " + pv + " was not identified!"
        )


def test_pvprop(pvobj_pvcheck: pvUtils):
    """Testing the reading of the text file and PV property rule"""
    lines = get_lines(rulefile)
    pvlist = pvobj_pvcheck.pvepics.pvstringlist
    assert pvlist.size() == lines, "Wrong PV list size extracted from input text file!"
    pvobj_pvcheck._checkValidFormat()
    pvobj_pvcheck._checkPropRules()
    for c, pv in enumerate(pvlist):
        if c > 18:
            assert not pvobj_pvcheck.VWarnD[pv], (
                "PV " + pv + ", rule warning not identified!"
            )
        else:
            assert not pvobj_pvcheck.VRuleD[pv], (
                "PV " + pv + ", rule failure not identified!"
            )
    assert pvobj_pvcheck.PVInternal == 2, "PV internal wrongly counted!"


def test_epicsdb(pvobj_pvdb: pvUtils):
    """Testing the parsing of the EPICS database"""
    pvlist = pvobj_pvdb.pvepics.pvstringlist
    assert pvlist.size() == 3, "Wrong PV list size extracted from EPICS Db file!"
    pvToReadFromDB = [
        "Sys-Sub:Dis-Dev-Idx:MyAnalogVar",
        "Sys-Sub:Dis-Dev-Idx:MyBoolVar",
        "Sys-Sub:Dis-Dev-Idx:MyWaveVar",
    ]
    assert list(pvlist) == pvToReadFromDB, "Wrong PV name extracted from EPICS Db file!"


def test_epicssubs(pvobj_pvsubs: pvUtils):
    """Testing the creating and parsing of an EPICS databse"""
    pvlist = pvobj_pvsubs.pvepics.pvstringlist
    assert (
        pvlist.size() == 3
    ), "Wrong PV list size extracted from EPICS Db using substitution file!"
    pvToReadFromDB = [
        "Sys-Sub:Dis-Dev-Idx:MyAnalogVar",
        "Sys-Sub:Dis-Dev-Idx:MyBoolVar",
        "Sys-Sub:Dis-Dev-Idx:MyWaveVar",
    ]
    assert (
        list(pvlist) == pvToReadFromDB
    ), "Wrong PV name extracted from EPICS Db using substitution file!"


def test_pvepics(pvobj_fromioc: pvUtils):
    """Testing the PV list size fetched from an IOC"""
    pvlist = pvobj_fromioc.pvepics.pvstringlist
    assert pvlist.size() == 10, "Wrong PV list size from IOC"


def test_backend(pvobj_backend: pvUtils):
    """Testing the reading of the text file, PV format, property and validation via naming service api"""
    lines = get_lines(apifile)
    pvlist = pvobj_backend.pvepics.pvstringlist
    assert pvlist.size() == lines, "Wrong PV list size extracted from input text file!"
    pvobj_backend._checkValidFormat()
    pvobj_backend._checkPropRules()
    pvobj_backend._checkValidName()
    assert len(pvobj_backend.VNameD) == lines, "Wrong PV Name dictionary size!"
    for pv in pvlist:
        assert not pvobj_backend.VNameD[pv], (
            "Not registered ESS Name " + pv + " was not identified!"
        )


def test_all(pvobj_all: pvUtils):
    """Test the entire PV validation sequence"""
    pvobj_all.run()
    w = b"The PVs with Rule Failure are = 0"
    c = tmpf1.read()
    assert w in c, "Wrong csv file created!"
    lines = get_lines(okfile)
    pvlist = pvobj_all.pvepics.pvstringlist
    assert pvlist.size() == lines, "Wrong PV list size extracted from input text file!"
    assert len(pvobj_all.VNameD) == lines, "Wrong PV Name dictionary size!"
    for pv in pvlist:
        assert pvobj_all.VNameD[pv], "Wrong PV " + pv + " validation!"

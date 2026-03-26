import pathlib
from os import environ
from time import sleep

import pytest
from run_iocsh import IOC

from pvValidatorUtils import epicsUtils, pvUtils

_test_dir = str(pathlib.Path(__file__).parent)
fmtfile = _test_dir + "/pvlist_fmt.txt"
rulefile = _test_dir + "/pvlist_rule.txt"
apifile = _test_dir + "/pvlist_api.txt"
okfile = _test_dir + "/pvlist_ok.txt"
epicsdbfile = [_test_dir + "/test.db", "P=Sys-Sub:,R=Dis-Dev-Idx:"]
subsfile = [_test_dir + "/test.substitutions", "PP=Sys-Sub:,RR=Dis-Dev-Idx:"]

# Rule/warning boundary: PVs at index 0-18 have rule failures,
# PVs at index >18 have rule warnings (matches pvlist_rule.txt layout)
RULE_FAIL_BOUNDARY = 18


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
def pvobj_all(tmp_path):
    """
    This fixture is to check the entire PV validation sequence
    The PV list is given from the text file okfile
    The PV validation outcome is written in a temporary CSV file
    """
    csvfile = str(tmp_path / "output.csv")
    pvepics = epicsUtils()
    pvu = pvUtils(pvepics=pvepics, pvfile=okfile, csvfile=csvfile)
    pvu._test_csvfile = csvfile  # expose for assertion in test
    return pvu


def get_lines(file):
    """Count PV lines in an input text file (skips comments and blank lines)."""
    with pathlib.Path(file).open() as f:
        return sum(
            1
            for line in f
            if not line.isspace()
            and not line.startswith("%")
            and not line.startswith("#")
        )


def test_pvformat(pvobj_pvfmt: pvUtils):
    """Testing the reading of the text file and PV format"""
    lines = get_lines(fmtfile)
    pvlist = pvobj_pvfmt.pvepics.pvstringlist
    assert pvlist.size() == lines, "Wrong PV list size extracted from input text file!"
    with pytest.raises(SystemExit):
        pvobj_pvfmt.run()
    assert len(pvobj_pvfmt.VFormD) == lines, "Wrong PV format dictionary size!"
    for pv in pvlist:
        assert not pvobj_pvfmt.VFormD[pv], (
            "Wrong format of PV " + pv + " should have been identified as invalid"
        )


def test_pvprop(pvobj_pvcheck: pvUtils):
    """Testing the reading of the text file and PV property rule"""
    lines = get_lines(rulefile)
    pvlist = pvobj_pvcheck.pvepics.pvstringlist
    assert pvlist.size() == lines, "Wrong PV list size extracted from input text file!"
    with pytest.raises(SystemExit):
        pvobj_pvcheck.run()
    for c, pv in enumerate(pvlist):
        if c > RULE_FAIL_BOUNDARY:
            assert not pvobj_pvcheck.VWarnD[pv], (
                "PV " + pv + " should have a rule warning"
            )
        else:
            assert not pvobj_pvcheck.VRuleD[pv], (
                "PV " + pv + " should have a rule failure"
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
    with open(pvobj_all._test_csvfile, "r") as f:
        c = f.read()
    assert "The PVs with Rule Failure are = 0" in c, "Wrong csv file created!"
    lines = get_lines(okfile)
    pvlist = pvobj_all.pvepics.pvstringlist
    assert pvlist.size() == lines, "Wrong PV list size extracted from input text file!"
    assert len(pvobj_all.VNameD) == lines, "Wrong PV Name dictionary size!"
    for pv in pvlist:
        assert pvobj_all.VNameD[pv], "Wrong PV " + pv + " validation!"

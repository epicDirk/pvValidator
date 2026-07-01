import pathlib
from os import environ
from time import sleep

import pytest

# NOTE: run_iocsh is imported lazily inside pvobj_fromioc (below), not here. A
# top-level `from run_iocsh import IOC` made the WHOLE module fail collection when
# run_iocsh was absent (it is an ESS-network-only extra installed with `|| true`),
# and `-k` does not help because it runs after collection. Only the epics_ioc test
# needs it, and that test is marker-skipped offline.
from pvValidatorUtils import epicsUtils, pvUtils

# Every test here drives the classic pvUtils pipeline, which builds an epicsUtils
# (SWIG) PV container — so the whole module needs the compiled extensions. conftest
# skips these when SWIG is absent (pure-Python checkout); they run in the e3/Docker image.
pytestmark = pytest.mark.swig

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
    from run_iocsh import IOC  # lazy import — only the epics_ioc test needs it

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
            # PVs after the boundary are warning-only: they MUST carry a rule warning.
            # (Previously this asserted `not VWarnD` — inverted — and the branch was
            #  dead because the file had no PVs past the boundary.)
            assert pvobj_pvcheck.VWarnD[pv], "PV " + pv + " should have a rule warning"
        else:
            assert not pvobj_pvcheck.VRuleD[pv], (
                "PV " + pv + " should have a rule failure"
            )
    assert pvobj_pvcheck.PVInternal == 2, "PV internal wrongly counted!"


def test_structural_error_is_status_effective(tmp_path):
    """P0 regression: a structural error (ELEM-6) must be status- and exit-effective.

    Previously the classic pipeline wrote structural findings to datainfo only, so
    an ELEM-6 error left VRuleD=True and exited 0. It must now fail the rule check.
    """
    f = tmp_path / "pvs.txt"
    f.write_text(
        "ABCDEFG-010:EMR-TT-001:Temperature\n"
    )  # System "ABCDEFG" = 7 chars -> ELEM-6
    pv = pvUtils(pvepics=epicsUtils(), checkonlyfmt=True, pvfile=str(f), stdout=True)
    with pytest.raises(SystemExit):  # errors -> SystemExit(1)
        pv.run()
    name = "ABCDEFG-010:EMR-TT-001:Temperature"
    assert pv.VRuleD[name] is False, "ELEM-6 structural error must fail the rule check"
    assert pv.exiterror is True


def test_mtca_warning_is_status_effective(tmp_path):
    """F2 regression: the classic pipeline must now run check_mtca_naming (EXC-MTCA).

    A non-3-digit MTCA index is a warning that used to be invisible in the legacy
    path; it must now surface as a rule warning (VWarnD=True) without a hard failure.
    """
    f = tmp_path / "pvs.txt"
    f.write_text(
        "PBI-BCM01:Ctrl-MTCA-12:Status\n"
    )  # MTCA index 12 (not 3 digits) -> EXC-MTCA
    pv = pvUtils(pvepics=epicsUtils(), checkonlyfmt=True, pvfile=str(f), stdout=True)
    pv.run()  # warnings only -> no SystemExit
    name = "PBI-BCM01:Ctrl-MTCA-12:Status"
    assert (
        pv.VWarnD[name] is True
    ), "MTCA warning must be status-effective in the classic path"
    assert pv.exiterror is False


def test_classic_short_setpoint_no_prop3(tmp_path):
    """Round 3 (E): the classic pipeline must strip -SP/-RB before the short-property
    whitelist, so a valid short setpoint like On-SP is not spuriously flagged PROP-3
    (previously it diverged from check_all_rules / the --format path)."""
    f = tmp_path / "pvs.txt"
    f.write_text(
        "LEBT:PBI-Dev-001:On-SP\n"
    )  # property "On-SP" -> effective "On" (known short)
    pv = pvUtils(pvepics=epicsUtils(), checkonlyfmt=True, pvfile=str(f), stdout=True)
    pv.run()  # clean -> no SystemExit
    name = "LEBT:PBI-Dev-001:On-SP"
    assert not pv.VWarnD.get(name), "On-SP must not get a PROP-3 short-property warning"
    assert pv.exiterror is False


def test_naming_unreachable_online_exits_nonzero(tmp_path, monkeypatch):
    """Round 3: online validation (-n, not --noapi) that cannot reach the naming
    service degrades to format-only + warning BUT must exit non-zero, so a CI gate
    does not silently pass names that were never verified against the registry."""
    from pvValidatorUtils import naming_client
    from pvValidatorUtils.exceptions import NamingServiceConnectionError

    def _unreachable(self):
        raise NamingServiceConnectionError("simulated outage")

    monkeypatch.setattr(
        naming_client.NamingServiceClient, "check_connectivity", _unreachable
    )
    f = tmp_path / "pvs.txt"
    f.write_text(
        "SEE-010:EMR-TT-001:Temperature\n"
    )  # format-valid; would pass format-only
    pv = pvUtils(pvepics=epicsUtils(), checkonlyfmt=False, pvfile=str(f), stdout=True)
    assert pv.checkonlyfmt is True, "unreachable service must degrade to format-only"
    assert pv.exiterror is True, "unverified online run must be exit-effective"
    with pytest.raises(SystemExit):
        pv.run()


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


@pytest.mark.epics_ioc
def test_pvepics(pvobj_fromioc: pvUtils):
    """Testing the PV list size fetched from an IOC"""
    pvlist = pvobj_fromioc.pvepics.pvstringlist
    # test.db has 3 records; EPICS auto-generates additional PVs per record
    # (count varies by EPICS base version: 10 in 7.0.7, 12 in 7.0.9+)
    assert pvlist.size() >= 3, "Too few PVs from IOC (expected at least 3 records)"
    assert pvlist.size() <= 20, "Unexpectedly many PVs from IOC"


@pytest.mark.ess_network
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


@pytest.mark.ess_network
def test_all(pvobj_all: pvUtils):
    """Test the entire PV validation sequence (queries the Naming Service → needs ESS network)"""
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

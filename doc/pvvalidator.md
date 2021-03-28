# pvValidator How To

[[_TOC_]]

## Introduction
**pvValidator** is a tool to help Integrators to validate the **Records Names** (aka **PVs**) defined in the **EPICS db** loaded by the **IOC**.

The validation rules implemented in the tool, are the ones described in the document [ESS Rules for EPICS PV Property](https://chess.esss.lu.se/enovia/link/ESS-3218463/21308.51166.39936.65207/valid), so we suggest to read that document before to use the tool.

As stated in the above documentation, in order to be **valid**, a PV must:
- follows the PV format and rules
- its device instance, or in the case of _high-level_ PV its System/Subsystem, be registered as **ESS Name** in the Naming Registry

The tool can perform **online** or **offline** validation. In online mode the tool can fetch all the PVs produced by a running IOC giving as input the host IP address, and optionally, the port if multiple IOCs are running in the same host (or the GUID in place of the IP:Port). In offline mode, the list of PVs are fetched from an input text file.

The tool can run in **interactive** mode showing on the screen, using the [curses](https://en.wikipedia.org/wiki/Curses_(programming_library)) library, the result of the validation outcome. The validation outcome can be saved in a csv file, skipping the interactive session, or even saved directly from the interactive session.

As default, the tool will connect to the production Naming Service API in order to perform the complete validation. If the Naming Service API cannot be reach, or if any other reason the connection to the Naming Service has to be postponed, the tool will only perform check on the PV Format and Rules.
## Running Options
Once compiled, the tool can be run from its CLI, called **pvValidator.py**.

The required options are `-d`, `-s` or `-i` which are mutually exclusive.

In the following paragraphs the description of each option.

---
### Help and Version
`> pvValidator.py -h`

Will shows the help message with the list of all available options

`> pvValidator.py -V`

Will shows the current version of the tool

---
### Discover Running IOCs
Running the tool with the discovery option (which is equivalent to the `pvlist` EPICS command line) it will print out the list of available IOCs reachable from the host with their GUID and IP:Port, e.g.
```shell
> pvValidator.py -d
GUID 0x0D63F85F00000000C82E9D36 version 2: tcp@[172.30.6.12:5075]
GUID 0x10AC5D600000000044DFFC32 version 2: tcp@[172.30.6.104:5075]
GUID 0x18ACF7A54835478A98FAE1EF version 1: tcp@[172.30.6.89:5075]
GUID 0x213B4B60000000000C86891D version 2: tcp@[172.30.5.147:5075]
GUID 0x38542A6000000000B2132B11 version 2: tcp@[172.30.4.33:5075]
GUID 0x385FF85F000000007957420B version 2: tcp@[172.30.4.104:49549]
GUID 0x385FF85F00000000ABD17D03 version 2: tcp@[172.30.4.104:5075]
```
Notice that depend how the EPICS gateways are setup in the host, you maybe cannot see all the available running IOCs, however if you can ping their IP you can still use it to fetch the PVs list.

---
### Interactive validation
**Online**

The **online** interactive validation can be done taken the list of PVs from running IOC,  using the following command

`> pvValidator.py -s <IP[:Port]>`

or

`> pvValidator.py -s <GUID>`

where `<IP[:Port]>` is the IP of the Host IOC, or the `<GUID>` is the IOC GUID that can be fecthed using the `-d` command.

E.g.

`> pvValidator.py -s 172.30.6.12`

`> pvValidator.py -s 172.30.4.104:49549`
in this last case the port is needed to identify the IOC from the others running in the host.
Or equivalently can be done using its GUID

`> pvValidtor.py -s 0x385FF85F000000007957420B`

The following syntax is allowed if you are running the tool in the same host where it is running the IOC.

`> pvValidator.py -s localhost`

**Offline**

When is not (yet) available a running IOC, the list of PVs can be given through a text file. Each line of the text file should have only one PV; comments can inserted putting the `%` character at the beginning of the line.
The command to do the **offline** validation in this case is the following

`> pvValidator.py -i <INPUTPVFILE>`

E.g.

`> pvValidator.py -i mypvfile.txt`

See the **Interactive Session Guide** below to have more detail about the interactive validation.

---
### Non Interactive validation
The outcome of the validation, as shown in the interactive session, can be saved directly in a csv file for further checking or just for record, thus skipping the interactive session.
For online validation

`> pvValidator.py -s <IP[:Port]> -o <CSVFILE>`

For offline validation

`> pvValidator.py -i <INPUTPVFILE> -o <CSVFILE>`

E.g.

`> pvValidator.py -s 172.30.6.12 -o myoutfile.csv`

or

`> pvValidator.py -i mypvfile.txt -o myoutfile.csv`

---
### Naming Service API
By default the tool will connect to the production Naming Service API to check the registration of each ESS Name as extracted from the PVs tp perform the validation.

Only for testing purpose, the validation can be done connecting the tool to the Development or the Staging Naming Serivce API, using the following option

`> pvValidator.py -s <IP[:Port]> -n {prod,dev,stag}`

E.g.

`> pvValidator.py -s 172.30.6.12 -n dev`

or

`> pvValidator.py -i mypvfile -n stag`

As it said before, the `-n prod` option is redundant as it is the default one.

If for any reason the validation through the Naming Service API cannot be done, the following option should be added

`> pVValidator.py -s 172.30.6.12 --noapi`

or

`> pVValidator.py -i mypvfile.txt --noapi`

Notice that the tool will not perform the complete validation, but it will just check if the PV follows any of the allowed format and if it follows the Property Rules.

***
## Interactive Session Guide
### Getting Started
The illustrative videos shown in this section are taken in offline mode option, i.e. using a text file as input pv list, and of course they are still valid if the online session mode is choosen.

![video1](GS.mp4)

**Validation Comments**

In the following table we summarize the validation comments as we are shown in the previous video

| Validation Comment | Meaning |Note|
|--------------------|---------|----|
|NOT VALID (Wrong Format)|The PV does not follow any valid ESS Name Format| if connected or not to Naming API<br>no further checks are done |
|NOT VALID (Name Fail)|The instance of the PV is not registered in the Naming Service<br> or some component of the instance (e.g. System, Subsystem, Discipline or Device)<br> is not approved in the Naming Service| only if connected to Naming API|
|NOT VALID (Name and Rule Fail) | The Name Fail occurs and the PV does not follow some of Property Rules | only if connectted to Naming API|
|NOT VALID (Rule Fail) | The Name Rule is ok but the PV does not follow some of the Property Rules.| only if connected to Naming API|
|VALID| The PV follows both Name and PV Property Rules| only if connected to Naming API|
|OK Format, Rule Fail| The PV follows some format but does not follow some of the Property Rules| if not connected to Naming API<br>no complete Validation check|
|OK Format, OK Rule| The PV followd both format and Property Rules|if not connected to Naming API<br>no complete Validation check|

As it was explained at the begining, if the Naming API connection is skipped, the complete validation cannot be perfomed.

### Keybindings

In the following video we shown the available keybindings, once pressed **F1**

![video2](keys.mp4)

### PV Validation details and Validation Summary

The following videos shows when **return** button is pressed over the highlited PV the validation details; by pressing the **v** the validation summary is shown. The first with the connection to the Naming API.

![video3](val1.mp4)

The second video is done without the conenction to the Naming API (i.e. the `--noapi` option was used)

![video4](val2.mp4)
### Search, Save , Sort and some display option

The following video shows some of the avaliable option like save the csv file, search in the table or change some display visualization.

![video5](misc.mp4)

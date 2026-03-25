/*************************************************************************\
* Copyright (c) 2010 UChicago Argonne LLC, as Operator of Argonne
* National Laboratory.
* Copyright (c) 2002 The Regents of the University of California, as
* Operator of Los Alamos National Laboratory.
* SPDX-License-Identifier: EPICS
* EPICS Base is distributed subject to a Software License Agreement found
* in the file LICENSE that is included with this distribution.
\*************************************************************************/

/* original code: epics-base/modules/pvAccess/pvtoolsSrc/pvlist.cpp */
/* Modified for pvValidator*/
/* Alfio Rizzo - alfio.rizzo@ess.eu*/
/* Mon Oct 11 04:12:32 PM CET 2021 */

#include <stdio.h>

#include <fstream>
#include <iostream>
#include <istream>
#include <iterator>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include <epicsGetopt.h>
#include <epicsStdlib.h>
#include <pv/logger.h>

#include <epicsExit.h>
#include <osiSock.h>

#include <pv/byteBuffer.h>
#include <pv/configuration.h>
#include <pv/inetAddressUtil.h>
#include <pv/pvaConstants.h>
#include <pv/remote.h>
#include <pv/rpcClient.h>
#include <pv/serializeHelper.h>
#include <pva/client.h>

using namespace std;

using namespace epics::pvData;
using namespace epics::pvAccess;

struct ServerEntry {
  string guid;
  string protocol;
  vector<osiSockAddr> addresses;
  int8 version;
};

class epicsUtils {
public:
  epicsUtils(string);
  epicsUtils(bool);
  epicsUtils();
  ~epicsUtils();
  vector<string> pvstringlist;
  string serverlist;
  string getServerList();
  string getVersion;
  string getAddress;

private:
#if defined(_WIN32) && !defined(_MINGW)
  FILE *popen(const char *, const char *);
  int pclose(FILE *);
#endif
  static const char lookup[16];
  string toHex(int8 *, size_t);
  std::size_t readSize(ByteBuffer *);
  string deserializeString(ByteBuffer *);
  typedef map<string, ServerEntry> ServerMap;
  ServerMap serverMap;
  bool processSearchResponse(osiSockAddr const &, ByteBuffer &);
  bool discoverServers(double);
  bool byGUIDSearch;
  double timeOut;
};

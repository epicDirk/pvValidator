/*
 * Copyright information and license terms for this software can be
 * found in the file LICENSE that is included with the distribution
 */

#include <stdio.h>

#include <iostream>
#include <map>
#include <iterator>
#include <vector>
#include <string>
#include <istream>
#include <fstream>
#include <sstream>


#include <epicsStdlib.h>
#include <epicsGetopt.h>
#include <pv/logger.h>

#include <epicsExit.h>
#include <osiSock.h>

#include <pv/byteBuffer.h>
#include <pv/serializeHelper.h>
#include <pv/pvaConstants.h>
#include <pv/inetAddressUtil.h>
#include <pv/configuration.h>
#include <pv/remote.h>
#include <pv/rpcClient.h>
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
        string HasAlias(string);
        string serverlist;
        string getServerList();
        string getVersion;
        string getAddress;
    private:
#if defined(_WIN32) && !defined(_MINGW)
        FILE *popen(const char*, const char *);
        int pclose(FILE *);
#endif
        static const char lookup[16];
        string toHex(int8* , size_t );
        std::size_t readSize(ByteBuffer* );
        string deserializeString(ByteBuffer* );
        typedef map<string, ServerEntry> ServerMap;
        ServerMap serverMap;
        bool processSearchResponse(osiSockAddr const & , ByteBuffer & );
        bool discoverServers(double );
        bool byGUIDSearch;
        double timeOut ;





};

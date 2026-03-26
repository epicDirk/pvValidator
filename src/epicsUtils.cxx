/*
 * Copyright information and license terms for this software can be
 * found in the file LICENSE that is included with the distribution
 */

#include "epicsUtils.h"

const char epicsUtils::lookup[16] = {'0', '1', '2', '3', '4', '5', '6', '7',
                                     '8', '9', 'A', 'B', 'C', 'D', 'E', 'F'};

epicsUtils::epicsUtils(bool servdisc) {
  timeOut = 3.0;
  SET_LOG_LEVEL(logLevelError);

  if (servdisc) {
    discoverServers(timeOut);
    stringstream ss;
    for (const auto &kv : serverMap) {
      const ServerEntry &entry = kv.second;

      ss << "GUID 0x" << entry.guid << " version " << (int)entry.version << ": "
         << entry.protocol << "@[ ";

      for (size_t i = 0; i < entry.addresses.size(); i++) {
        ss << inetAddressToString(entry.addresses[i]);
        if (i < (entry.addresses.size() - 1))
          ss << " ";
      }
      ss << " ]\n";
    }
    serverlist = ss.str();
    if (serverlist.length() == 0)
      serverlist = "IOC Server(s) not available";
  }
};

epicsUtils::epicsUtils(string serverAddress) {
  timeOut = 3.0;
  SET_LOG_LEVEL(logLevelError);

  if (serverAddress.length() == 0) {
    throw std::runtime_error("The server address cannot be empty string");
  }
  getAddress = serverAddress;
  // by GUID search
  if (serverAddress.length() == 26 && serverAddress[0] == '0' &&
      serverAddress[1] == 'x')
    byGUIDSearch = true;
  else
    byGUIDSearch = false;

  if (byGUIDSearch)
    discoverServers(timeOut);

  // by GUID search

  if (byGUIDSearch) {
    string originalGUID = serverAddress;
    bool resolved = false;
    for (const auto &kv : serverMap) {
      const ServerEntry &entry = kv.second;

      if (strncmp(entry.guid.c_str(), &(originalGUID[2]), 24) == 0) {
        // found match
        if (!entry.addresses.empty()) {
          // TODO for now we take only first server address
          serverAddress = inetAddressToString(entry.addresses[0]);
          resolved = true;
        }
      }
    }

    if (!resolved) {
      throw std::runtime_error(string("Failed to resolve GUID '") + originalGUID + "'");
    }
  }

  StructureConstPtr argstype(getFieldCreate()
                                 ->createFieldBuilder()
                                 ->setId("epics:nt/NTURI:1.0")
                                 ->add("scheme", pvString)
                                 ->add("path", pvString)
                                 ->addNestedStructure("query")
                                 ->add("op", pvString)
                                 ->endNested()
                                 ->createStructure());

  PVStructure::shared_pointer args(
      getPVDataCreate()->createPVStructure(argstype));

  args->getSubFieldT<PVString>("scheme")->put("pva");
  args->getSubFieldT<PVString>("path")->put("server");
  args->getSubFieldT<PVString>("query.op")->put("channels");

  PVStructure::shared_pointer ret;
  try {
    RPCClient rpc("server", createRequest("field()"),
                  ChannelProvider::shared_pointer(), serverAddress);

    ret = rpc.request(args, timeOut, true);
  } catch (std::exception &e) {
    throw std::runtime_error(string("EPICS RPC error: ") + e.what());
  }

  PVStringArray::shared_pointer pvs(ret->getSubField<PVStringArray>("value"));
  if (!pvs)
    throw std::runtime_error("Server response missing 'value' field");

  PVStringArray::const_svector val(pvs->view());

  std::copy(val.begin(), val.end(), std::back_inserter(pvstringlist));
};

string epicsUtils::getServerList() { return serverlist; }

// HasAlias() removed — was dead code (fully commented out, never called)

epicsUtils::~epicsUtils() {}

#if defined(_WIN32) && !defined(_MINGW)
FILE epicsUtils::*popen(const char *command, const char *mode) {
  return _popen(command, mode);
}
int epicsUtils::pclose(FILE *stream) { return _pclose(stream); }
#endif

/// Get hex representation of byte.
string epicsUtils::toHex(int8 *ba, size_t len) {
  string sb;

  for (size_t i = 0; i < len; i++) {
    int8 b = ba[i];

    int upper = (b >> 4) & 0x0F;
    sb += lookup[upper];

    int lower = b & 0x0F;
    sb += lookup[lower];
  }

  return sb;
}

std::size_t epicsUtils::readSize(ByteBuffer *buffer) {
  int8 b = buffer->getByte();
  if (b == -1)
    return -1;
  else if (b == -2) {
    int32 s = buffer->getInt();
    if (s < 0)
      THROW_BASE_EXCEPTION("negative size");
    return s;
  } else
    return (std::size_t)(b < 0 ? b + 256 : b);
}

string epicsUtils::deserializeString(ByteBuffer *buffer) {

  std::size_t size = /*SerializeHelper::*/ readSize(buffer);
  if (size !=
      (size_t)-1) // TODO null strings check, to be removed in the future
  {
    // entire string is in buffer, simply create a string out of it (copy)
    if (size > buffer->getRemaining())
      THROW_BASE_EXCEPTION("string size exceeds buffer remaining");
    std::size_t pos = buffer->getPosition();
    string str(buffer->getBuffer() + pos, size);
    buffer->setPosition(pos + size);
    return str;
  } else
    return std::string();
}

// return true if new server response is recevived
bool epicsUtils::processSearchResponse(osiSockAddr const &responseFrom,
                                       ByteBuffer &receiveBuffer) {
  // first byte is PVA_MAGIC
  int8 magic = receiveBuffer.getByte();
  if (magic != PVA_MAGIC)
    return false;

  // second byte version
  int8 version = receiveBuffer.getByte();
  if (version == 0) {
    // 0 -> 1 included incompatible changes
    return false;
  }

  // only data for UDP
  int8 flags = receiveBuffer.getByte();
  if (flags < 0) {
    // 7-bit set
    receiveBuffer.setEndianess(EPICS_ENDIAN_BIG);
  } else {
    receiveBuffer.setEndianess(EPICS_ENDIAN_LITTLE);
  }

  // command ID and paylaod
  int8 command = receiveBuffer.getByte();
  if (command != (int8)0x04)
    return false;

  int32 rawPayloadSize = receiveBuffer.getInt();
  if (rawPayloadSize < 0)
    return false;
  size_t payloadSize = (size_t)rawPayloadSize;
  if (payloadSize < (12 + 4 + 16 + 2))
    return false;
  if (receiveBuffer.getRemaining() < payloadSize)
    return false;

  epics::pvAccess::ServerGUID guid;
  receiveBuffer.get(guid.value, 0, sizeof(guid.value));

  /*int32 searchSequenceId = */ receiveBuffer.getInt();

  osiSockAddr serverAddress;
  memset(&serverAddress, 0, sizeof(serverAddress));
  serverAddress.ia.sin_family = AF_INET;

  // 128-bit IPv6 address
  if (!decodeAsIPv6Address(&receiveBuffer, &serverAddress))
    return false;

  // accept given address if explicitly specified by sender
  if (serverAddress.ia.sin_addr.s_addr == INADDR_ANY)
    serverAddress.ia.sin_addr = responseFrom.ia.sin_addr;

  // NOTE: htons might be a macro (e.g. vxWorks)
  int16 port = receiveBuffer.getShort();
  serverAddress.ia.sin_port = htons(port);

  string protocol = /*SerializeHelper::*/ deserializeString(&receiveBuffer);

  /*bool found =*/receiveBuffer.getByte(); // != 0;

  string guidString = toHex((int8 *)guid.value, sizeof(guid.value));

  ServerMap::iterator iter = serverMap.find(guidString);
  if (iter != serverMap.end()) {
    bool found = false;
    vector<osiSockAddr> &vec = iter->second.addresses;
    for (const auto &ai : vec)
      if (sockAddrAreIdentical(&ai, &serverAddress)) {
        found = true;
        break;
      }

    if (!found) {
      vec.push_back(serverAddress);
      return true;
    } else
      return false;
  } else {
    ServerEntry serverEntry;
    serverEntry.guid = guidString;
    serverEntry.protocol = protocol;
    serverEntry.addresses.push_back(serverAddress);
    serverEntry.version = version;

    serverMap[guidString] = serverEntry;

    return true;
  }
}

bool epicsUtils::sendBroadcast(SOCKET socket, ByteBuffer &sendBuffer,
                               InetAddrVector &broadcastAddresses) {
  bool oneOK = false;
  for (size_t i = 0; i < broadcastAddresses.size(); i++) {
    if (pvAccessIsLoggable(logLevelDebug)) {
      char strBuffer[64];
      sockAddrToDottedIP(&broadcastAddresses[i].sa, strBuffer,
                         sizeof(strBuffer));
      LOG(logLevelDebug, "UDP Tx (%zu) -> %s", sendBuffer.getPosition(),
          strBuffer);
    }

    int status = ::sendto(socket, sendBuffer.getBuffer(),
                          sendBuffer.getPosition(), 0,
                          &broadcastAddresses[i].sa, sizeof(sockaddr));
    if (status < 0) {
      char errStr[64];
      epicsSocketConvertErrnoToString(errStr, sizeof(errStr));
      fprintf(stderr, "Send error: %s\n", errStr);
    } else
      oneOK = true;
  }
  return oneOK;
}

bool epicsUtils::discoverServers(double timeOut) {
  osiSockAttach();

  SOCKET socket = epicsSocketCreate(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
  if (socket == INVALID_SOCKET) {
    char errStr[64];
    epicsSocketConvertErrnoToString(errStr, sizeof(errStr));
    fprintf(stderr, "Failed to create a socket: %s\n", errStr);
    return false;
  }

  //
  // read config
  //

  Configuration::shared_pointer configuration(new SystemConfigurationImpl());

  string addressList =
      configuration->getPropertyAsString("EPICS_PVA_ADDR_LIST", "");
  bool autoAddressList =
      configuration->getPropertyAsBoolean("EPICS_PVA_AUTO_ADDR_LIST", true);
  int broadcastPort = configuration->getPropertyAsInteger(
      "EPICS_PVA_BROADCAST_PORT", PVA_BROADCAST_PORT);

  // query broadcast addresses of all IFs
  InetAddrVector broadcastAddresses;
  {
    IfaceNodeVector ifaces;
    if (discoverInterfaces(ifaces, socket, 0)) {
      fprintf(stderr, "Unable to populate interface list\n");
      epicsSocketDestroy(socket);
      return false;
    }

    for (const auto &iface : ifaces) {
      if (iface.validBcast && iface.bcast.sa.sa_family == AF_INET) {
        osiSockAddr bcast = iface.bcast;
        bcast.ia.sin_port = htons(broadcastPort);
        broadcastAddresses.push_back(bcast);
      }
    }
  }

  // set broadcast address list
  if (!addressList.empty()) {
    // if auto is true, add it to specified list
    InetAddrVector *appendList = 0;
    if (autoAddressList)
      appendList = &broadcastAddresses;

    InetAddrVector list;
    getSocketAddressList(list, addressList, broadcastPort, appendList);
    if (!list.empty()) {
      // delete old list and take ownership of a new one
      broadcastAddresses = list;
    }
  }

  for (size_t i = 0; i < broadcastAddresses.size(); i++)
    LOG(logLevelDebug, "Broadcast address #%zu: %s.", i,
        inetAddressToString(broadcastAddresses[i]).c_str());

  // ---

  int optval = 1;
  int status = ::setsockopt(socket, SOL_SOCKET, SO_BROADCAST, (char *)&optval,
                            sizeof(optval));
  if (status) {
    char errStr[64];
    epicsSocketConvertErrnoToString(errStr, sizeof(errStr));
    fprintf(stderr, "Error setting SO_BROADCAST: %s\n", errStr);
    epicsSocketDestroy(socket);
    return false;
  }

  osiSockAddr bindAddr;
  memset(&bindAddr, 0, sizeof(bindAddr));
  bindAddr.ia.sin_family = AF_INET;
  bindAddr.ia.sin_port = htons(0);
  bindAddr.ia.sin_addr.s_addr = htonl(INADDR_ANY);

  status = ::bind(socket, (sockaddr *)&(bindAddr.sa), sizeof(sockaddr));
  if (status) {
    char errStr[64];
    epicsSocketConvertErrnoToString(errStr, sizeof(errStr));
    fprintf(stderr, "Failed to bind: %s\n", errStr);
    epicsSocketDestroy(socket);
    return false;
  }

  // set timeout
#ifdef _WIN32
  // ms
  DWORD timeout = 250;
#else
  struct timeval timeout;
  memset(&timeout, 0, sizeof(struct timeval));
  timeout.tv_sec = 0;
  timeout.tv_usec = 250000;
#endif
  status = ::setsockopt(socket, SOL_SOCKET, SO_RCVTIMEO, (char *)&timeout,
                        sizeof(timeout));
  if (status) {
    char errStr[64];
    epicsSocketConvertErrnoToString(errStr, sizeof(errStr));
    fprintf(stderr, "Error setting SO_RCVTIMEO: %s\n", errStr);
    epicsSocketDestroy(socket);
    return false;
  }

  osiSockAddr responseAddress;
  osiSocklen_t sockLen = sizeof(sockaddr);
  // read the actual socket info
  status = ::getsockname(socket, &responseAddress.sa, &sockLen);
  if (status) {
    char errStr[64];
    epicsSocketConvertErrnoToString(errStr, sizeof(errStr));
    fprintf(stderr, "Failed to get local socket address: %s.", errStr);
    epicsSocketDestroy(socket);
    return false;
  }

  char buffer[1024];
  ByteBuffer sendBuffer(buffer, sizeof(buffer) / sizeof(char));

  sendBuffer.putByte(PVA_MAGIC);
  sendBuffer.putByte(PVA_CLIENT_PROTOCOL_REVISION);
  sendBuffer.putByte((EPICS_BYTE_ORDER == EPICS_ENDIAN_BIG)
                         ? 0x80
                         : 0x00);                // data + 7-bit endianess
  sendBuffer.putByte((int8_t)CMD_SEARCH);        // search
  sendBuffer.putInt(4 + 1 + 3 + 16 + 2 + 1 + 2); // "zero" payload

  sendBuffer.putInt(0); // sequenceId
  sendBuffer.putByte(
      (int8_t)0x81); // reply required // TODO unicast vs multicast; for now we
                     // mark ourselves as unicast
  sendBuffer.putByte((int8_t)0);   // reserved
  sendBuffer.putShort((int16_t)0); // reserved

  // NOTE: is it possible (very likely) that address is any local address
  // ::ffff:0.0.0.0
  encodeAsIPv6Address(&sendBuffer, &responseAddress);
  sendBuffer.putShort((int16_t)ntohs(responseAddress.ia.sin_port));

  sendBuffer.putByte((int8_t)0x00); // protocol count
  sendBuffer.putShort((int16_t)0);  // name count

  if (!sendBroadcast(socket, sendBuffer, broadcastAddresses)) {
    epicsSocketDestroy(socket);
    return false;
  }

  char rxbuff[1024];
  ByteBuffer receiveBuffer(rxbuff, sizeof(rxbuff) / sizeof(char));

  osiSockAddr fromAddress;
  osiSocklen_t addrStructSize = sizeof(sockaddr);

  int sendCount = 0;

  while (true) {
    receiveBuffer.clear();

    // receive packet from socket
    int bytesRead = ::recvfrom(socket, (char *)receiveBuffer.getBuffer(),
                               receiveBuffer.getRemaining(), 0,
                               (sockaddr *)&fromAddress, &addrStructSize);

    if (bytesRead > 0) {
      if (pvAccessIsLoggable(logLevelDebug)) {
        char strBuffer[64];
        sockAddrToDottedIP(&fromAddress.sa, strBuffer, sizeof(strBuffer));
        LOG(logLevelDebug, "UDP Rx (%d) <- %s", bytesRead, strBuffer);
      }
      receiveBuffer.setPosition(bytesRead);
      receiveBuffer.flip();

      processSearchResponse(fromAddress, receiveBuffer);

    } else {
      if (bytesRead == -1) {
        int socketError = SOCKERRNO;

        // interrupted or timeout
        if (socketError == SOCK_EINTR ||
            socketError == EAGAIN || // no alias in libCom
            // windows times out with this
            socketError == SOCK_ETIMEDOUT || socketError == SOCK_EWOULDBLOCK) {
          // OK
        } else if (socketError == SOCK_ECONNREFUSED || // avoid spurious
                                                       // ECONNREFUSED in Linux
                   socketError == SOCK_ECONNRESET) // or ECONNRESET in Windows
        {
          // OK
        } else {
          // unexpected error
          char errStr[64];
          epicsSocketConvertErrnoToString(errStr, sizeof(errStr));
          fprintf(stderr, "Socket recv error: %s\n", errStr);
          break;
        }
      }

      if (++sendCount < 3) {
        if (!sendBroadcast(socket, sendBuffer, broadcastAddresses)) {
          epicsSocketDestroy(socket);
          return false;
        }
      } else
        break;
    }
  }

  // TODO shutdown sockets?
  // TODO this resouce is not released on failure
  epicsSocketDestroy(socket);

  return true;
}

epicsUtils::epicsUtils() {
  stringstream ss;
  Version pvaver("pvAccess", "cpp", EPICS_PVA_MAJOR_VERSION,
                 EPICS_PVA_MINOR_VERSION, EPICS_PVA_MAINTENANCE_VERSION,
                 EPICS_PVA_DEVELOPMENT_FLAG);
  Version pvdver("pvData", "cpp", EPICS_PVD_MAJOR_VERSION,
                 EPICS_PVD_MINOR_VERSION, EPICS_PVD_MAINTENANCE_VERSION,
                 EPICS_PVD_DEVELOPMENT_FLAG);

  ss << "Compiled with EPICS:\n\t" << EPICS_VERSION_FULL << "\n";
  ss << "\t" << pvaver.getVersionString() << "\n";
  ss << "\t" << pvdver.getVersionString() << "\n";

  getVersion = ss.str();
};

/*************************************************************************\
* Copyright (c) 2010 UChicago Argonne LLC, as Operator of Argonne
* National Laboratory.
* Copyright (c) 2002 The Regents of the University of California, as
* Operator of Los Alamos National Laboratory.
* SPDX-License-Identifier: EPICS
* EPICS Base is distributed subject to a Software License Agreement found
* in the file LICENSE that is included with this distribution.
\*************************************************************************/

/* msi - macro substitutions and include */
/* original code: epics-base/modules/database/src/ioc/dbtemplate/msi.cpp */
/* Modified for pvValidator*/
/* Alfio Rizzo - alfio.rizzo@ess.eu*/
/* Fri Nov  8 02:26:42 PM CET 2024 */

#include <list>
#include <stdexcept>
#include <string>

#include <ctype.h>
#include <errno.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <dbDefs.h>
#include <epicsString.h>
#include <errlog.h>
#include <macLib.h>
#include <osiFileName.h>
#include <osiUnistd.h>

#define MAX_BUFFER_SIZE 4096
#define MAX_DEPS 1024

typedef struct inputFile {
  std::string filename;
  FILE *fp;
  int lineNum;
} inputFile;

typedef struct inputData {
  std::list<inputFile> inputFileList;
  std::list<std::string> pathList;
  char inputBuffer[MAX_BUFFER_SIZE];
  inputData() {
    memset(inputBuffer, 0, sizeof(inputBuffer) * sizeof(inputBuffer[0]));
  };
} inputData;

typedef enum {
  tokenLBrace,
  tokenRBrace,
  tokenSeparator,
  tokenString,
  tokenEOF
} tokenType;

typedef struct subFile {
  std::string substitutionName;
  FILE *fp;
  int lineNum;
  char inputBuffer[MAX_BUFFER_SIZE];
  char *pnextChar;
  tokenType token;
  char string[MAX_BUFFER_SIZE];
} subFile;

// /* Module to read the substitution file */
typedef struct subInfo {
  subFile *psubFile;
  bool isFile;
  char *filename;
  bool isPattern;
  std::list<std::string> patternList;
  std::string macroReplacements;
  subInfo()
      : psubFile(NULL), isFile(false), filename(NULL), isPattern(false) {};
} subInfo;

class msiUtils {
public:
  msiUtils();
  msiUtils(std::string, std::string, std::string, bool);
  ~msiUtils();
  int createDB();
  std::string stringdb;

private:
  /*Global variables */
  static int opt_V;
  static bool opt_D;
  static char *outFile;
  static int numDeps, depHashes[];
  static const char *cmdNames[];
  /*Local variables*/
  std::string m_substitutionName;
  std::string m_templatePath;
  std::string m_subsMacro;
  bool m_localScope;
  /* Module to read the template files */
  static void inputConstruct(inputData **);
  static void inputDestruct(inputData *const);
  static void inputOpenFile(inputData *, const char *const);
  static void inputCloseFile(inputData *);
  static void inputCloseAllFiles(inputData *);
  static void inputAddPath(inputData *const, const char *const);
  static void inputBegin(inputData *const, const char *const);
  static char *inputNextLine(inputData *const);
  static void inputNewIncludeFile(inputData *const, const char *const);
  static void inputErrPrint(const inputData *const);
  static void substituteOpen(subInfo **, const std::string &);
  static tokenType subGetNextToken(subFile *);
  static char *subGetNextLine(subFile *);
  static void subFileErrPrint(subFile *, const char *);
  static void catMacroReplacements(subInfo *, const char *);
  static void substituteDestruct(subInfo *const);
  static bool substituteGetNextSet(subInfo *const, char **);
  static bool substituteGetGlobalSet(subInfo *const);
  static const char *substituteGetReplacements(subInfo *const);
  static const char *substituteGetGlobalReplacements(subInfo *const);
  static void freeSubFile(subInfo *);
  static void freePattern(subInfo *);
  typedef enum { cmdInclude, cmdSubstitute } cmdType;
  // /* Forward references to local routines */
  static void abortExit(const int);
  static void addMacroReplacements(MAC_HANDLE *const, const char *const);
  void makeSubstitutions(inputData *const, MAC_HANDLE *const,
                         const char *const);
};

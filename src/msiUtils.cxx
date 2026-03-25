/*
 * Copyright information and license terms for this software can be
 * found in the file LICENSE that is included with the distribution
 */

#include "msiUtils.h"

/*Global variables */
const char *msiUtils::cmdNames[2] = {"include", "substitute"};
char *msiUtils::outFile = 0;
int msiUtils::numDeps = 0, msiUtils::depHashes[MAX_DEPS];
int msiUtils::opt_V = 0;
bool msiUtils::opt_D = false;

msiUtils::msiUtils() {

};

msiUtils::~msiUtils() {

};

msiUtils::msiUtils(std::string substitutionName, std::string templatePath,
                   std::string subsMacro, bool localScope) {
  m_substitutionName = substitutionName;
  m_templatePath = templatePath;
  m_subsMacro = subsMacro;
  m_localScope = localScope;
  stringdb = "";
};

int msiUtils::createDB() {
  inputData *inputPvt;
  MAC_HANDLE *macPvt;
  inputConstruct(&inputPvt);
  macCreateHandle(&macPvt, 0);
  inputAddPath(inputPvt, m_templatePath.c_str());
  addMacroReplacements(macPvt, m_subsMacro.c_str());
  subInfo *substitutePvt;
  char *filename = 0;
  bool isGlobal, isFile;
  macSuppressWarning(macPvt, 1);
  substituteOpen(&substitutePvt, m_substitutionName);
  do {
    isGlobal = substituteGetGlobalSet(substitutePvt);
    if (isGlobal) {
      const char *macStr = substituteGetGlobalReplacements(substitutePvt);
      if (macStr)
        addMacroReplacements(macPvt, macStr);
    } else if ((isFile = substituteGetNextSet(substitutePvt, &filename))) {

      if (!filename) {
        fprintf(stderr, "msi: No template file\n");
        _Exit(10);
      }

      const char *macStr;
      while ((macStr = substituteGetReplacements(substitutePvt))) {
        if (m_localScope)
          macPushScope(macPvt);

        addMacroReplacements(macPvt, macStr);
        makeSubstitutions(inputPvt, macPvt, filename);

        if (m_localScope)
          macPopScope(macPvt);
      }
    }
  } while (isGlobal || isFile);
  substituteDestruct(substitutePvt);
  macDeleteHandle(macPvt);
  errlogFlush(); // macLib calls errlogPrintf()
  inputDestruct(inputPvt);
  fflush(stdout);
  return opt_V & 2;
}

void msiUtils::inputCloseAllFiles(inputData *pinputData) {

  const std::list<inputFile> &inFileList = pinputData->inputFileList;
  while (!inFileList.empty()) {
    inputCloseFile(pinputData);
  }
}

void msiUtils::inputCloseFile(inputData *pinputData) {
  std::list<inputFile> &inFileList = pinputData->inputFileList;

  if (!inFileList.empty()) {
    inputFile &inFile = inFileList.front();
    if (fclose(inFile.fp))
      fprintf(stderr, "msi: Can't close input file '%s'\n",
              inFile.filename.c_str());
    inFileList.erase(inFileList.begin());
  }
}

void msiUtils::inputErrPrint(const inputData *const pinputData) {

  fprintf(stderr, "input: '%s' at ", pinputData->inputBuffer);
  const std::list<inputFile> &inFileList = pinputData->inputFileList;
  std::list<inputFile>::const_iterator inFileIt = inFileList.begin();
  while (inFileIt != inFileList.end()) {
    fprintf(stderr, "line %d of ", inFileIt->lineNum);

    if (!inFileIt->filename.empty()) {
      fprintf(stderr, " file %s\n", inFileIt->filename.c_str());
    } else {
      fprintf(stderr, "stdin:\n");
    }

    if (++inFileIt != inFileList.end()) {
      fprintf(stderr, "  included from ");
    } else {
      fprintf(stderr, "\n");
    }
  }
  fprintf(stderr, "\n");
}

void msiUtils::inputNewIncludeFile(inputData *const pinputData,
                                   const char *const name) {

  inputOpenFile(pinputData, name);
}

void msiUtils::inputOpenFile(inputData *pinputData,
                             const char *const filename) {
  std::list<std::string> &pathList = pinputData->pathList;
  std::list<std::string>::iterator pathIt = pathList.end();
  std::string fullname;
  FILE *fp = 0;

  if (!filename) {
    fp = stdin;
  } else if (pathList.empty() || strchr(filename, '/')) {
    fp = fopen(filename, "r");
  } else {
    pathIt = pathList.begin();
    while (pathIt != pathList.end()) {
      fullname = *pathIt + "/" + filename;
      fp = fopen(fullname.c_str(), "r");
      if (fp)
        break;
      ++pathIt;
    }
  }

  if (!fp) {
    fprintf(stderr, ERL_ERROR " msi: Can't open file '%s'\n", filename);
    inputErrPrint(pinputData);
    abortExit(1);
  }

  inputFile inFile = inputFile();

  if (pathIt != pathList.end()) {
    inFile.filename = fullname;
  } else if (filename) {
    inFile.filename = filename;
  } else {
    inFile.filename = "stdin";
  }

  if (opt_D) {
    int hash = epicsStrHash(inFile.filename.c_str(), 12345);
    int i = 0;
    int match = 0;

    while (i < numDeps) {
      if (hash == depHashes[i++]) {
        match = 1;
        break;
      }
    }
    if (!match) {
      const char *wrap = numDeps ? " \\\n" : "";

      printf("%s %s", wrap, inFile.filename.c_str());
      if (numDeps < MAX_DEPS) {
        depHashes[numDeps++] = hash;
      } else {
        fprintf(stderr, "msi: More than %d dependencies!\n", MAX_DEPS);
        depHashes[0] = hash;
      }
    }
  }

  inFile.fp = fp;
  pinputData->inputFileList.push_front(inFile);
}

// Duplicate free function inputAddPath() removed — identical to msiUtils::inputAddPath() below

void msiUtils::inputAddPath(inputData *const pinputData,
                            const char *const path) {
  const char *pcolon;
  const char *pdir;
  size_t len;
  const char sep = *OSI_PATH_LIST_SEPARATOR;

  pdir = path;
  /*an empty name at beginning, middle, or end means current directory*/
  while (pdir && *pdir) {
    bool emptyName = (*pdir == sep);
    if (emptyName)
      ++pdir;

    std::string directory;
    if (!emptyName) {
      pcolon = strchr(pdir, sep);
      len = (pcolon ? (pcolon - pdir) : strlen(pdir));
      if (len > 0) {
        directory = std::string(pdir, len);
        pdir = pcolon;
        /*unless at end skip past first colon*/
        if (pdir && *(pdir + 1) != 0)
          ++pdir;
      } else { /*must have been trailing : */
        emptyName = true;
      }
    }

    if (emptyName) {
      directory = ".";
    }

    pinputData->pathList.push_back(directory);
  }
}

void msiUtils::inputBegin(inputData *const pinputData,
                          const char *const fileName) {

  inputCloseAllFiles(pinputData);
  inputOpenFile(pinputData, fileName);
}

char *msiUtils::inputNextLine(inputData *const pinputData) {
  std::list<inputFile> &inFileList = pinputData->inputFileList;

  while (!inFileList.empty()) {
    inputFile &inFile = inFileList.front();
    char *pline = fgets(pinputData->inputBuffer, MAX_BUFFER_SIZE, inFile.fp);
    if (pline) {
      ++inFile.lineNum;
      return pline;
    }
    inputCloseFile(pinputData);
  }
  return 0;
}

void msiUtils::inputConstruct(inputData **ppvt) { *ppvt = new inputData; }

void msiUtils::inputDestruct(inputData *const pinputData) {
  inputCloseAllFiles(pinputData);
  delete (pinputData);
}

void msiUtils::abortExit(const int status) {
  if (outFile) {
    fclose(stdout);
    unlink(outFile);
  }
  exit(status);
}

/*start of code that handles substitution file*/
void msiUtils::substituteOpen(subInfo **ppvt,
                              const std::string &substitutionName) {
  subInfo *psubInfo;
  subFile *psubFile;
  FILE *fp;

  psubInfo = new subInfo;
  *ppvt = psubInfo;
  psubFile = new subFile;
  psubInfo->psubFile = psubFile;

  fp = fopen(substitutionName.c_str(), "r");
  if (!fp) {
    fprintf(stderr, ERL_ERROR " msi: Can't open file '%s'\n",
            substitutionName.c_str());
    abortExit(1);
  }

  psubFile->substitutionName = substitutionName;
  psubFile->fp = fp;
  psubFile->lineNum = 1;
  psubFile->inputBuffer[0] = 0;
  psubFile->pnextChar = &psubFile->inputBuffer[0];
  subGetNextToken(psubFile);
}

tokenType msiUtils::subGetNextToken(subFile *psubFile) {
  char *p, *pto;

  p = psubFile->pnextChar;
  if (!p) {
    psubFile->token = tokenEOF;
    goto done;
  }

  if (*p == 0 || *p == '\n' || *p == '#') {
    p = subGetNextLine(psubFile);
    psubFile->token = p ? tokenSeparator : tokenEOF;
    goto done;
  }

  while (isspace((int)*p))
    p++;
  if (*p == '{') {
    psubFile->token = tokenLBrace;
    psubFile->pnextChar = ++p;
    goto done;
  }
  if (*p == '}') {
    psubFile->token = tokenRBrace;
    psubFile->pnextChar = ++p;
    goto done;
  }
  if (*p == 0 || isspace((int)*p) || *p == ',') {
    while (isspace((int)*p) || *p == ',')
      p++;
    psubFile->token = tokenSeparator;
    psubFile->pnextChar = p;
    goto done;
  }
  /*now handle quoted strings*/
  if (*p == '"') {
    pto = &psubFile->string[0];
    *pto++ = *p++;
    while (*p != '"') {
      if (*p == 0 || *p == '\n') {
        subFileErrPrint(psubFile, "Strings must be on single line\n");
        abortExit(1);
      }
      /*allow  escape for embedded quote*/
      if ((p[0] == '\\') && p[1] == '"') {
        *pto++ = *p++;
        *pto++ = *p++;
        continue;
      }
      *pto++ = *p++;
    }
    *pto++ = *p++;
    psubFile->pnextChar = p;
    *pto = 0;
    psubFile->token = tokenString;
    goto done;
  }

  /*Now take anything up to next non String token and not space*/
  pto = &psubFile->string[0];

  while (!isspace((int)*p) && (strspn(p, "\",{}") == 0))
    *pto++ = *p++;
  *pto = 0;

  psubFile->pnextChar = p;
  psubFile->token = tokenString;

done:
  return psubFile->token;
}

char *msiUtils::subGetNextLine(subFile *psubFile) {
  char *pline;

  do {
    pline = fgets(psubFile->inputBuffer, MAX_BUFFER_SIZE, psubFile->fp);
    ++psubFile->lineNum;
  } while (pline && psubFile->inputBuffer[0] == '#');

  if (!pline) {
    psubFile->token = tokenEOF;
    psubFile->inputBuffer[0] = 0;
    psubFile->pnextChar = 0;
    return 0;
  }

  psubFile->pnextChar = &psubFile->inputBuffer[0];
  return &psubFile->inputBuffer[0];
}

void msiUtils::subFileErrPrint(subFile *psubFile, const char *message) {
  fprintf(stderr, "msi: %s\n", message);
  fprintf(stderr, "  in substitution file '%s' at line %d:\n  %s",
          psubFile->substitutionName.c_str(), psubFile->lineNum,
          psubFile->inputBuffer);
}

void msiUtils::substituteDestruct(subInfo *const psubInfo) {

  freeSubFile(psubInfo);
  freePattern(psubInfo);
  delete (psubInfo);
}

void msiUtils::freeSubFile(subInfo *psubInfo) {
  subFile *psubFile = psubInfo->psubFile;

  if (psubFile->fp) {
    if (fclose(psubFile->fp))
      fprintf(stderr, "msi: Can't close substitution file\n");
  }
  delete (psubFile);
  free(psubInfo->filename);
  psubInfo->psubFile = 0;
}

void msiUtils::freePattern(subInfo *psubInfo) {

  psubInfo->patternList.clear();
  psubInfo->isPattern = false;
}

bool msiUtils::substituteGetNextSet(subInfo *const psubInfo, char **filename) {
  subFile *psubFile = psubInfo->psubFile;

  *filename = 0;
  while (psubFile->token == tokenSeparator)
    subGetNextToken(psubFile);

  if (psubFile->token == tokenEOF) {

    return false;
  }

  if (psubFile->token == tokenString && strcmp(psubFile->string, "file") == 0) {
    size_t len;

    psubInfo->isFile = true;
    if (subGetNextToken(psubFile) != tokenString) {
      subFileErrPrint(psubFile, "Parse error, expecting a filename");
      abortExit(1);
    }

    freePattern(psubInfo);
    free(psubInfo->filename);

    len = strlen(psubFile->string);
    if (psubFile->string[0] == '"' && psubFile->string[len - 1] == '"') {
      psubFile->string[len - 1] = '\0';
      psubInfo->filename = macEnvExpand(psubFile->string + 1);
    } else
      psubInfo->filename = macEnvExpand(psubFile->string);

    while (subGetNextToken(psubFile) == tokenSeparator)
      ;

    if (psubFile->token != tokenLBrace) {
      subFileErrPrint(psubFile, "Parse error, expecting '{'");
      abortExit(1);
    }
    subGetNextToken(psubFile);
  }
  *filename = psubInfo->filename;

  while (psubFile->token == tokenSeparator)
    subGetNextToken(psubFile);

  if (psubFile->token == tokenLBrace) {
    return true;
  }

  if (psubFile->token == tokenRBrace) {
    subFileErrPrint(psubFile, "Parse error, unexpected '}'");
    abortExit(1);
  }

  if (psubFile->token != tokenString ||
      strcmp(psubFile->string, "pattern") != 0) {
    subFileErrPrint(psubFile, "Parse error, expecting 'pattern'");
    abortExit(1);
  }

  freePattern(psubInfo);
  psubInfo->isPattern = true;

  while (subGetNextToken(psubFile) == tokenSeparator)
    ;

  if (psubFile->token != tokenLBrace) {
    subFileErrPrint(psubFile, "Parse error, expecting '{'");
    abortExit(1);
  }

  while (true) {
    while (subGetNextToken(psubFile) == tokenSeparator)
      ;

    if (psubFile->token != tokenString)
      break;

    psubInfo->patternList.push_back(psubFile->string);
  }

  if (psubFile->token != tokenRBrace) {
    subFileErrPrint(psubFile, "Parse error, expecting '}'");
    abortExit(1);
  }

  subGetNextToken(psubFile);
  return true;
}

bool msiUtils::substituteGetGlobalSet(subInfo *const psubInfo) {
  subFile *psubFile = psubInfo->psubFile;

  while (psubFile->token == tokenSeparator)
    subGetNextToken(psubFile);
  if (psubFile->token == tokenString &&
      strcmp(psubFile->string, "global") == 0) {
    subGetNextToken(psubFile);
    return true;
  }

  return false;
}

const char *msiUtils::substituteGetReplacements(subInfo *const psubInfo) {
  subFile *psubFile = psubInfo->psubFile;

  psubInfo->macroReplacements.clear();

  while (psubFile->token == tokenSeparator)
    subGetNextToken(psubFile);

  if (psubFile->token == tokenRBrace && psubInfo->isFile) {
    psubInfo->isFile = false;
    free(psubInfo->filename);
    psubInfo->filename = 0;
    freePattern(psubInfo);
    subGetNextToken(psubFile);

    return 0;
  }

  if (psubFile->token == tokenEOF) {

    return 0;
  }

  if (psubFile->token != tokenLBrace) {

    return 0;
  }

  if (psubInfo->isPattern) {
    bool gotFirstPattern = false;

    while (subGetNextToken(psubFile) == tokenSeparator)
      ;
    std::list<std::string> &patternList = psubInfo->patternList;
    std::list<std::string>::iterator patternIt = patternList.begin();
    while (true) {
      if (psubFile->token == tokenRBrace) {
        subGetNextToken(psubFile);
        return psubInfo->macroReplacements.c_str();
      }

      if (psubFile->token != tokenString) {
        subFileErrPrint(psubFile, "Parse error, expecting macro value");
        abortExit(1);
      }

      if (gotFirstPattern)
        catMacroReplacements(psubInfo, ",");
      gotFirstPattern = true;

      if (patternIt != patternList.end()) {
        catMacroReplacements(psubInfo, patternIt->c_str());
        catMacroReplacements(psubInfo, "=");
        catMacroReplacements(psubInfo, psubFile->string);
        ++patternIt;
      } else {
        subFileErrPrint(psubFile, "Warning, too many values given");
      }

      while (subGetNextToken(psubFile) == tokenSeparator)
        ;
    }
  } else
    while (true) {
      switch (subGetNextToken(psubFile)) {
      case tokenRBrace:
        subGetNextToken(psubFile);
        return psubInfo->macroReplacements.c_str();

      case tokenSeparator:
        catMacroReplacements(psubInfo, ",");
        break;

      case tokenString:
        catMacroReplacements(psubInfo, psubFile->string);
        break;

      case tokenLBrace:
        subFileErrPrint(psubFile, "Parse error, unexpected '{'");
        abortExit(1);
      case tokenEOF:
        subFileErrPrint(psubFile, "Parse error, incomplete file?");
        abortExit(1);
      }
    }
}

const char *msiUtils::substituteGetGlobalReplacements(subInfo *const psubInfo) {
  subFile *psubFile = psubInfo->psubFile;

  psubInfo->macroReplacements.clear();

  while (psubFile->token == tokenSeparator)
    subGetNextToken(psubFile);

  if (psubFile->token == tokenRBrace && psubInfo->isFile) {
    psubInfo->isFile = false;
    free(psubInfo->filename);
    psubInfo->filename = 0;
    freePattern(psubInfo);
    subGetNextToken(psubFile);

    return 0;
  }

  if (psubFile->token == tokenEOF) {

    return 0;
  }
  if (psubFile->token != tokenLBrace) {

    return 0;
  }

  while (true) {
    switch (subGetNextToken(psubFile)) {
    case tokenRBrace:
      subGetNextToken(psubFile);
      return psubInfo->macroReplacements.c_str();

    case tokenSeparator:
      catMacroReplacements(psubInfo, ",");
      break;

    case tokenString:
      catMacroReplacements(psubInfo, psubFile->string);
      break;

    case tokenLBrace:
      subFileErrPrint(psubFile, "Parse error, unexpected '{'");
      abortExit(1);
    case tokenEOF:
      subFileErrPrint(psubFile, "Parse error, incomplete file?");
      abortExit(1);
    }
  }
}

void msiUtils::addMacroReplacements(MAC_HANDLE *const macPvt,
                                    const char *const pval) {
  char **pairs;
  long status;

  status = macParseDefns(macPvt, pval, &pairs);
  if (status == -1) {
    fprintf(stderr, "msi: Error from macParseDefns\n");
    _Exit(10);
  }
  if (status) {
    status = macInstallMacros(macPvt, pairs);
    if (!status) {
      fprintf(stderr, ERL_ERROR " from macInstallMacros\n");
      _Exit(10);
    }
    free(pairs);
  }
}

void msiUtils::catMacroReplacements(subInfo *psubInfo, const char *value) {

  psubInfo->macroReplacements += value;
}

void msiUtils::makeSubstitutions(inputData *const inputPvt,
                                 MAC_HANDLE *const macPvt,
                                 const char *const templateName) {
  char *input;
  static char buffer[MAX_BUFFER_SIZE];
  int n;

  inputBegin(inputPvt, templateName);
  while ((input = inputNextLine(inputPvt))) {
    int expand = 1;
    char *p;
    char *command = 0;

    p = input;
    /*skip whitespace at beginning of line*/
    while (*p && (isspace((int)*p)))
      ++p;

    /*Look for i or s */
    if (*p && (*p == 'i' || *p == 's'))
      command = p;

    if (command) {
      char *pstart;
      char *pend;
      int cmdind = -1;
      size_t i;

      for (i = 0; i < NELEMENTS(cmdNames); i++) {
        if (strstr(command, cmdNames[i])) {
          cmdind = (int)i;
        }
      }
      if (cmdind < 0)
        goto endcmd;
      p = command + strlen(cmdNames[cmdind]);
      /*skip whitespace after command*/
      while (*p && (isspace((int)*p)))
        ++p;
      /*Next character must be quote*/
      if ((*p == 0) || (*p != '"'))
        goto endcmd;
      pstart = ++p;
      /*Look for end quote*/
      while (*p && (*p != '"')) {
        /*allow escape for embedded quote*/
        if ((p[0] == '\\') && p[1] == '"') {
          p += 2;
          continue;
        } else {
          if (*p == '"')
            break;
        }
        ++p;
      }
      pend = p;
      if (*p == 0)
        goto endcmd;
      /*skip quote and any trailing blanks*/
      while (*++p == ' ')
        ;
      if (*p != '\n' && *p != 0)
        goto endcmd;
      std::string copy = std::string(pstart, pend);

      switch (cmdind) {
      case cmdInclude:
        inputNewIncludeFile(inputPvt, copy.c_str());
        break;

      case cmdSubstitute:
        addMacroReplacements(macPvt, copy.c_str());
        break;

      default:
        fprintf(stderr, "msi: Logic error in makeSubstitutions\n");
        inputErrPrint(inputPvt);
        abortExit(1);
      }
      expand = 0;
    }

  endcmd:
    if (expand && !opt_D) {
      n = macExpandString(macPvt, input, buffer, MAX_BUFFER_SIZE - 1);
      stringdb += buffer;
      if (opt_V == 1 && n < 0) {
        fprintf(stderr, "msi: Error - undefined macros present\n");
        opt_V++;
      }
    }
  }
}

/* epicsUtils.i */
%module epicsUtils
%include <std_string.i>
%include <std_vector.i>
%include <exception.i>

/* Translate C++ exceptions to Python RuntimeError */
%exception {
  try {
    $action
  } catch (const std::exception& e) {
    SWIG_exception(SWIG_RuntimeError, e.what());
  }
}

namespace std {
    %template(VectorInt) vector<int>;
    %template(VectorDouble) vector<double>;
    %template(VectorString) vector<string>;
};

/* Tell SWIG about EPICS namespaces used in the header */
namespace epics {
    namespace pvData {}
    namespace pvAccess {}
}

%{
#include "epicsUtils.h"
%}

%include "epicsUtils.h"

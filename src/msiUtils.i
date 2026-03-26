/* msiUtils.i */
%module msiUtils
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

%{
#include "msiUtils.h"
%}

%include "msiUtils.h"

/* epicsUtils.i */
%module epicsUtils
%include <std_string.i>
%include <std_vector.i>



namespace std {
    %template(VectorInt) vector<int>;
    %template(VectorDouble) vector<double>;
    %template(VectorString) vector<string>;
};

namespace epics{
    namespace pvData{

    }
    namespace pvAccess{
        
    }
}


%{
#include "epicsUtils.h"

%}

%include "epicsUtils.h"


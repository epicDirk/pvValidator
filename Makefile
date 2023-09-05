# Author: Alfio Rizzo

EPICS=$(EPICS_BASE)
ARCH=$(EPICS_HOST_ARCH)
CMOD=epicsUtils
MOD = pvValidatorUtils
PYBIND = $(PYBINDPATH)





PYTHON_VERSION_MIN = "(3,6,0)"
PYTHON_VERSION :=$(shell python3 --version)
PYTHON_VERSION_OK :=$(shell python3 -c 'import sys; print(sys.version_info >= eval($(PYTHON_VERSION_MIN)))' )
MY_SETUPTOOLS = $(shell python3 -c 'import setuptools' 2>&1)


ifeq ($(findstring ModuleNotFoundError,$(MY_SETUPTOOLS)),ModuleNotFoundError)
$(error "Module setuptools not found!")
endif

ifeq ($(PYTHON_VERSION_OK),False)
$(error "Need Python >= $(PYTHON_VERSION_MIN), found $(PYTHON_VERSION)")
endif


ifndef PYBINDPATH
$(error PYBINDPATH is not set)
endif

ifndef EPICS_BASE
$(error Source your EPICS env)
endif



SRC = src
LIB = lib

EPICSINC = -I$(EPICS)/include -I$(EPICS)/include/compiler/gcc -I$(EPICS)/include/pv\
 -I$(EPICS)/include/os/Linux -I$(SRC)

INC = $(EPICSINC) -I$(PYBIND)


LPATH= $(EPICS)/lib/$(ARCH)
ELIBS = -L$(LPATH) -lpvAccessCA -lpvAccess -lpvData -lca -lCom





all: swig $(MOD)/_$(CMOD).so



swig: $(SRC)/$(CMOD).i
	swig -c++ -outdir $(MOD) -python $<



$(SRC)/%.o: $(SRC)/%.cxx $(SRC)/$(CMOD).h
	@echo "compiling $@..."
	g++ -O2 -fPIC $(INC) $(CFLAGS) -c $< -o $@


$(SRC)/$(CMOD)_wrap.o: $(SRC)/$(CMOD)_wrap.cxx
	@echo "compiling $@..."
	g++ -O2 -fPIC $(INC) $(CFLAGS) -c $< -o $@


$(MOD)/_$(CMOD).so: $(SRC)/$(CMOD).o $(SRC)/$(CMOD)_wrap.o
	@echo "creating shared library $@..."
	g++ -shared $(CFLAGS) $^ -o $@ -Wl,-rpath=$(LPATH) $(ELIBS)


.PHONY: all test clean

clean:
	rm -fr $(SRC)/*.o $(MOD)/_$(CMOD).so $(MOD)/$(CMOD).py $(SRC)/$(CMOD)_wrap.cxx build dist $(MOD).egg*

install:
	python3 setup.py install --user
test:
	pytest -ra

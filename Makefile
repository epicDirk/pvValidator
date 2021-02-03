EPICS=$(EPICS_BASE)
ARCH=$(EPICS_HOST_ARCH)
CMOD=epicsUtils
MOD = pvValidatorUtils
PYBIND = $(PYBINDPATH)

SRC = src
LIB = lib

EPICSINC = -I$(EPICS)/include -I$(EPICS)/include/compiler/gcc -I$(EPICS)/include/pv\
 -I$(EPICS)/include/os/Linux -I$(SRC)  

INC = $(EPICSINC) -I$(PYBIND)

ifeq ($(findstring python2,$(PYBIND)),python2)
	PY = python2
endif

ifeq ($(findstring python3,$(PYBIND)),python3)
	PY = python3
endif


LPATH= $(EPICS)/lib/$(ARCH)
ELIBS = -L$(LPATH) -lpvAccessCA -lpvAccess -lpvData -lca -lCom



all: swig $(MOD)/_$(CMOD).so



swig: $(SRC)/$(CMOD).i
	swig -c++ -outdir $(MOD) -python $<



$(SRC)/%.o: $(SRC)/%.cxx $(SRC)/$(CMOD).h 
	@echo "compiling $@..."
	g++ -O2 -fPIC $(INC) -c $< -o $@


$(SRC)/$(CMOD)_wrap.o: $(SRC)/$(CMOD)_wrap.cxx 
	@echo "compiling $@..."
	g++ -O2 -fPIC $(INC) -c $< -o $@


$(MOD)/_$(CMOD).so: $(SRC)/$(CMOD).o $(SRC)/$(CMOD)_wrap.o
	@echo "creating shared library $@..."
	g++ -shared $^ -o $@ -Wl,-rpath=$(LPATH) $(ELIBS)



clean:
	rm -fr $(SRC)/*.o $(MOD)/_$(CMOD).so $(MOD)/$(CMOD).py $(SRC)/$(CMOD)_wrap.cxx build dist $(MOD).egg*

install:  
	$(PY) setup.py install --user



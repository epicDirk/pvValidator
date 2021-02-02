EPICS=$(EPICS_BASE)
ARCH=$(EPICS_HOST_ARCH)
CMOD=epicsUtils
MOD = pvValidatorUtils
INCPY2 = -I/usr/include/python2.7
INCPY3 = -I/usr/include/python3.7
SRC = src
LIB = lib

EPICSINC = -I$(EPICS)/include -I$(EPICS)/include/compiler/gcc -I$(EPICS)/include/pv\
 -I$(EPICS)/include/os/Linux -I$(SRC)  


ifdef PY2
    INC = $(EPICSINC) $(INCPY2)
    PY = python2
else
    INC = $(EPICSINC) $(INCPY3)
    PY = python
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



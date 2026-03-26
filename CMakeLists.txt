#----------------------------------------------------------------------------
# Author: Alfio Rizzo - Sat 24 Apr 2021 09:02:57 AM CEST


#----------------------------------------------------------------------------
# Setup the project
cmake_minimum_required(VERSION 3.12 FATAL_ERROR)
project(pvValidator)

#----------------------------------------------------------------------------


if (NOT DEFINED ENV{EPICS_BASE})
    message(FATAL_ERROR "$EPICS_BASE not defined! Source before your EPICS Environment, Exit.")
else()
    message(STATUS "$EPICS_BASE defined")
endif()




find_package(SWIG REQUIRED)

set(MY_PYTHON_VERSION "" CACHE STRING "Optional user-selected Python version")
if(MY_PYTHON_VERSION)
    find_package(Python ${MY_PYTHON_VERSION} EXACT REQUIRED COMPONENTS Interpreter Development)
else()
  find_package(Python 3.8 REQUIRED COMPONENTS Interpreter Development)
endif()


set(NO_PIP_VENV "" CACHE STRING "Optional to skip creation of virtual environment" )

if (NO_PIP_VENV)
    set(PIP_BREAK_OPTION "--break-system-packages")
else()
    set(PIP_BREAK_OPTION "")
endif()

execute_process (
    COMMAND ${Python_EXECUTABLE} -c "import setuptools"
    RESULT_VARIABLE NO_PYTHON_SETUPTOOLS
    ERROR_QUIET
)


if (NO_PYTHON_SETUPTOOLS)
    message(FATAL_ERROR "Missing Python setuptools module! Please install them. Exit.")
else()
    message(STATUS "Python module setuptools installed")
endif()

execute_process (
    COMMAND ${Python_EXECUTABLE} -c "import pip"
    RESULT_VARIABLE NO_PIP_INSTALLED
    ERROR_QUIET
)

if (NO_PIP_INSTALLED)
    message(FATAL_ERROR "Missing pip package! Please install it. Exit.")
else()
    message(STATUS "pip package installed")
endif()



set(CMAKE_SHARED_LIBRARY_PREFIX "_")
set(MOD pvValidatorUtils)
set(CMOD epicsUtils)
set(MSI msiUtils)

set(EPICS $ENV{EPICS_BASE})
set(ARCH $ENV{EPICS_HOST_ARCH})
if (NOT ARCH)
    message(FATAL_ERROR "$EPICS_HOST_ARCH not defined! Source your EPICS Environment. Exit.")
endif()

set(CMAKE_CXX_STANDARD 11)

set(EPICSLIB -L${EPICS}/lib/${ARCH} -lpvAccessCA -lpvAccess -lpvData -lca -lCom)
set(CMAKE_INSTALL_RPATH ${EPICS}/lib/${ARCH})

file(COPY ${PROJECT_SOURCE_DIR}/${MOD} DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
file(COPY ${PROJECT_SOURCE_DIR}/pyproject.toml DESTINATION ${CMAKE_CURRENT_BINARY_DIR})


add_custom_command(OUTPUT ${PROJECT_SOURCE_DIR}/src/${CMOD}_wrap.cxx ${CMAKE_CURRENT_BINARY_DIR}/${MOD}/${CMOD}.py
    COMMAND swig -c++ -outdir ${CMAKE_CURRENT_BINARY_DIR}/${MOD} -python ${PROJECT_SOURCE_DIR}/src/${CMOD}.i
    )

add_custom_command(OUTPUT ${PROJECT_SOURCE_DIR}/src/${MSI}_wrap.cxx ${CMAKE_CURRENT_BINARY_DIR}/${MOD}/${MSI}.py
    COMMAND swig -c++ -outdir ${CMAKE_CURRENT_BINARY_DIR}/${MOD} -python ${PROJECT_SOURCE_DIR}/src/${MSI}.i
    )


# NOTE: compiler/gcc and os/Linux paths are EPICS conventions for the e3 Docker environment
include_directories(${PROJECT_SOURCE_DIR}/src/pv ${PROJECT_SOURCE_DIR}/src ${EPICS}/include
    ${EPICS}/include/compiler/gcc ${EPICS}/include/pv ${EPICS}/include/os/Linux
    ${Python_INCLUDE_DIRS}
    ${PROJECT_SOURCE_DIR}/src
    ${PROJECT_SOURCE_DIR}/src/pv)




enable_testing()

add_library(${CMOD} SHARED ${PROJECT_SOURCE_DIR}/src/${CMOD}_wrap.cxx ${PROJECT_SOURCE_DIR}/src/${CMOD}.cxx )
add_library(${MSI} SHARED ${PROJECT_SOURCE_DIR}/src/${MSI}_wrap.cxx ${PROJECT_SOURCE_DIR}/src/${MSI}.cxx)
target_link_libraries(${CMOD} ${EPICSLIB})
target_link_libraries(${MSI} ${EPICSLIB})

add_test(NAME pvValidatorTest COMMAND pytest -ra ${PROJECT_SOURCE_DIR} WORKING_DIRECTORY ${PROJECT_SOURCE_DIR})



install(TARGETS ${CMOD} ${MSI} DESTINATION ${CMAKE_CURRENT_BINARY_DIR}/${MOD})

install(CODE "execute_process(COMMAND ${Python_EXECUTABLE} -m pip install ${CMAKE_CURRENT_BINARY_DIR} ${PIP_BREAK_OPTION})")

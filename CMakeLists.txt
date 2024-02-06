#----------------------------------------------------------------------------
# Author: Alfio Rizzo - Sat 24 Apr 2021 09:02:57 AM CEST


#----------------------------------------------------------------------------
# Setup the project
cmake_minimum_required(VERSION 3.0 FATAL_ERROR)
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


set(EPICS $ENV{EPICS_BASE})
set(ARCH $ENV{EPICS_HOST_ARCH})

set(EPICSLIB -L${EPICS}/lib/${ARCH} -lpvAccessCA -lpvAccess -lpvData -lca -lCom)
set(CMAKE_INSTALL_RPATH ${EPICS}/lib/${ARCH})



file(COPY ${PROJECT_SOURCE_DIR}/${MOD} DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
file(COPY ${PROJECT_SOURCE_DIR}/pyproject.toml DESTINATION ${CMAKE_CURRENT_BINARY_DIR})


add_custom_command(OUTPUT ${PROJECT_SOURCE_DIR}/src/${CMOD}_wrap.cxx ${CMAKE_CURRENT_BINARY_DIR}/${MOD}/${CMOD}.py
    COMMAND swig -c++ -outdir ${CMAKE_CURRENT_BINARY_DIR}/${MOD} -python ${PROJECT_SOURCE_DIR}/src/${CMOD}.i
    )




include_directories(${PROJECT_SOURCE_DIR}/src/pv ${PROJECT_SOURCE_DIR}/src ${EPICS}/include
    ${EPICS}/include/compiler/gcc ${EPICS}/include/pv ${EPICS}/include/os/Linux
    ${Python_INCLUDE_DIRS}
    ${PROJECT_SOURCE_DIR}/src
    ${PROJECT_SOURCE_DIR}/src/pv)




enable_testing()

add_library(${CMOD} SHARED ${PROJECT_SOURCE_DIR}/src/${CMOD}_wrap.cxx ${PROJECT_SOURCE_DIR}/src/${CMOD}.cxx)
target_link_libraries(${CMOD} ${EPICSLIB})


add_test(NAME pvValidatorTest COMMAND pytest -ra ${PROJECT_SOURCE_DIR} WORKING_DIRECTORY ${PROJECT_SOURCE_DIR})

install(TARGETS ${CMOD} DESTINATION ${CMAKE_CURRENT_BINARY_DIR}/${MOD})

#install(CODE "execute_process(COMMAND ${Python_EXECUTABLE} -m pip install ${CMAKE_CURRENT_BINARY_DIR})")

install(CODE "execute_process(COMMAND pipx install ${CMAKE_CURRENT_BINARY_DIR})")

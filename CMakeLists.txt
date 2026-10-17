# =============================================================================
# MechWarrior 3 - static recompilation host (32-bit, MSVC x86)
#
#   py -3 run_lift.py        # -> src/recomp/gen/  (needs work/functions.json)
#   build.cmd                # vcvarsall amd64_x86 + CMake + Ninja -> build/mw3.exe
#   build\mw3.exe            # dry run: map and bind Mech3.exe
# =============================================================================
cmake_minimum_required(VERSION 3.20)
# The C runtime linked in (/MT): mw3.exe runs on a PC (or a netlab test VM)
# without the x86 Visual C++ redistributable.
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
project(mw3 C)

if(NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
  message(FATAL_ERROR "the host must be 32-bit: use build.cmd (vcvarsall amd64_x86)")
endif()
if(NOT MSVC)
  message(FATAL_ERROR "runtime/native32 is MSVC x86 inline assembly")
endif()
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE RelWithDebInfo)
endif()

set(PCRECOMP "${CMAKE_SOURCE_DIR}/../tools" CACHE PATH "pcrecomp checkout")
file(GLOB GEN_SOURCES CONFIGURE_DEPENDS "${CMAKE_SOURCE_DIR}/src/recomp/gen/*.c")
if(NOT GEN_SOURCES)
  message(FATAL_ERROR "src/recomp/gen is empty -- run Setup.cmd (or `py -3 run_lift.py`) first")
endif()

add_executable(mw3
  src/runtime/host.c
  ${PCRECOMP}/runtime/native32/native32.c
  ${PCRECOMP}/runtime/recomp32/image_loader.c
  ${PCRECOMP}/runtime/recomp32/recomp_trace.c
  ${GEN_SOURCES}
)
target_include_directories(mw3 PRIVATE
  src/runtime src/recomp/gen ${PCRECOMP}/runtime/native32 ${PCRECOMP}/runtime/recomp32)
# RECOMP_RETADDR=0u: a stack imbalance during bring-up leaks a harmless 0, not
# 0xDEAD0000 into a size argument (forcecommander).
target_compile_definitions(mw3 PRIVATE RECOMP_RETADDR=0u _CRT_SECURE_NO_WARNINGS
                                       RECOMP_FLAT_MEMORY RECOMP_LOCAL_REGS)
# Linked high and not relocatable, so Mech3.exe's 0x00400000..0x009EE000 is
# free for the guest image.
target_link_options(mw3 PRIVATE /BASE:0x60000000 /FIXED:NO /DYNAMICBASE:NO
                                /NXCOMPAT /LARGEADDRESSAWARE /STACK:0x1000000 /MANIFESTUAC:NO)
set(GEN_OPT "/O2" CACHE STRING "optimisation for the generated C")
# Visual Studio 2026's compiler (19.50 and later) drops the sign test of a
# 16-bit value shifted to the top of a register; Red Alert 2 crashed on it.
if(MSVC_VERSION GREATER_EQUAL 1950)
  string(APPEND GEN_OPT ";/d2SSAOptimizer-")
endif()
set_source_files_properties(${GEN_SOURCES} PROPERTIES COMPILE_OPTIONS "/w;${GEN_OPT}")
set_source_files_properties(src/runtime/host.c PROPERTIES COMPILE_OPTIONS "/W3")
target_link_libraries(mw3 PRIVATE user32 gdi32 kernel32 advapi32 vfw32)

option(MW3_TRACE "record a ring buffer of lifted function entries" OFF)
if(MW3_TRACE)
  target_compile_definitions(mw3 PRIVATE RECOMP_TRACE=1)
endif()

# MechWarrior 3 - Static Recompilation
# Phase 2: compile the generated x86->C translation units.
#
# Builds the recompiled code as a static library (validates compilation without
# the full runtime). Phase 3 will add the Win32/MFC42 runtime + an executable
# target (register/memory model, import bridges, CRT init), mirroring the sister
# Crimson Skies project.
#
# Generate first, then build 32-bit (x86):
#   py -3.11 run_pipeline.py
#   cmake -B build -A Win32 && cmake --build build
cmake_minimum_required(VERSION 3.20)
project(mw3_recomp C)

if(NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
    message(FATAL_ERROR "Build as 32-bit x86: cmake -B build -A Win32")
endif()

set(CMAKE_C_STANDARD 11)

file(GLOB RECOMP_GENERATED_SOURCES "src/recomp/gen/recomp_*.c")
if(NOT RECOMP_GENERATED_SOURCES)
    message(FATAL_ERROR "No generated sources. Run: py -3.11 run_pipeline.py")
endif()

add_library(mw3_recomp STATIC ${RECOMP_GENERATED_SOURCES})

target_include_directories(mw3_recomp PRIVATE src/recomp src/recomp/gen)

set_source_files_properties(${RECOMP_GENERATED_SOURCES} PROPERTIES
    COMPILE_DEFINITIONS "RECOMP_GENERATED_CODE")

if(MSVC)
    target_compile_options(mw3_recomp PRIVATE
        /GS- /bigobj /W3 /wd4244 /wd4018 /wd4146 /wd4305 /wd4267 /wd4090 /wd4102)
endif()

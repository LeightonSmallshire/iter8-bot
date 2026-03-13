# Determine Architecture
if(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|arm64")
    set(DPP_ARCH "aarch64")
else()
    set(DPP_ARCH "x86_64")
endif()

# Determine Configuration
if(NOT CMAKE_BUILD_TYPE)
    set(DPP_CONFIG "Release")
else()
    set(DPP_CONFIG ${CMAKE_BUILD_TYPE})
endif()

# Determine lib location
if(WIN32)
    set(DPP_DIR_NAME "Windows-${CMAKE_BUILD_TYPE}-${DPP_ARCH}")
else()
    # Reuse the same .so files for release/debug on linux
    set(DPP_DIR_NAME "Linux-${DPP_ARCH}")
endif()


set(DPP_BASE "${CMAKE_SOURCE_DIR}/thirdparty_v2")

# Locate Headers
find_path(DPP_INCLUDE_DIR
    NAMES dpp/dpp.h
    PATHS "${DPP_BASE}/include"
    NO_DEFAULT_PATH
)

# Locate Library 
# "${DPP_BASE}/bin/${DPP_DIR_NAME}" is for runtime, don't link directly
find_file(DPP_LIBRARY
    NAMES "libdpp.so" "libdpp.so.10" "libdpp.so.10.1" "libdpp.so.10.1.4"
    PATHS "${DPP_BASE}/lib/${DPP_DIR_NAME}"
    NO_DEFAULT_PATH
)

# Helpful debugging:
message( "DPP_ARCH        : ${DPP_ARCH}" )
message( "DPP_CONFIG      : ${DPP_CONFIG}" )
message( "DPP_DIR_NAME    : ${DPP_DIR_NAME}" )
message( "DPP_BASE        : ${DPP_BASE}" )
message( "DPP_INCLUDE_DIR : ${DPP_INCLUDE_DIR}" )
message( "DPP_LIBRARY     : ${DPP_LIBRARY}" )

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(DPP REQUIRED_VARS DPP_LIBRARY DPP_INCLUDE_DIR)

if(DPP_FOUND)
    add_library(dpp::dpp UNKNOWN IMPORTED)
    set_target_properties(dpp::dpp PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${DPP_INCLUDE_DIR}"
        IMPORTED_LOCATION "${DPP_LIBRARY}"
    )

    if(WIN32)
        # Windows needs the .lib for linking but the .dll for the location
        set_target_properties(dpp::dpp PROPERTIES 
            IMPORTED_IMPLIB "${DPP_LIBRARY}"
            IMPORTED_LOCATION "${DPP_BASE}/bin/${DPP_DIR_NAME}/dpp.dll"
        )
    endif()
endif()

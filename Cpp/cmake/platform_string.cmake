# Determine architecture
string(TOLOWER "${CMAKE_SYSTEM_NAME}" CMAKE_SYSTEM_NAME_LOWER)
string(TOLOWER "${CMAKE_SYSTEM_PROCESSOR}" CMAKE_SYSTEM_PROCESSOR_LOWER)


if(CMAKE_SYSTEM_PROCESSOR_LOWER MATCHES "x86_64|amd64")
    set(ARCH "amd64")
elseif(CMAKE_SYSTEM_PROCESSOR_LOWER MATCHES "aarch64|arm64")
    set(ARCH "arm64")
elseif(CMAKE_SYSTEM_PROCESSOR_LOWER MATCHES "i386|i686")
    set(ARCH "x86")
else()
    message(FATAL_ERROR "unsupported architecture ${CMAKE_SYSTEM_PROCESSOR}")
endif()

# Use "Debug" or "Release" depending on the current configuration
if(CMAKE_BUILD_TYPE)
    string(TOLOWER "${CMAKE_BUILD_TYPE}" CONFIG_SUFFIX)
else()
    # For multi-config generators (like Visual Studio), use generator expression
    set(CONFIG_SUFFIX "$<$<CONFIG:Debug>:debug>$<$<CONFIG:Release>:release>")
endif()


set(PLATFORM_STRING   "${CMAKE_SYSTEM_NAME_LOWER}_${ARCH}_${CONFIG_SUFFIX}"         )
set(PLATFORM_INCLUDES "${CMAKE_SOURCE_DIR}/thirdparty/include/"                )
set(PLATFORM_LIBS     "${CMAKE_SOURCE_DIR}/thirdparty/lib/${PLATFORM_STRING}/" )
set(PLATFORM_BINS     "${CMAKE_SOURCE_DIR}/thirdparty/bin/${PLATFORM_STRING}/" )

message("${PLATFORM_STRING}")
message("${PLATFORM_INCLUDES}")
message("${PLATFORM_LIBS}")
message("${PLATFORM_BINS}")

# Check if bin directory exists
if(NOT (EXISTS "${PLATFORM_INCLUDES}" AND IS_DIRECTORY "${PLATFORM_INCLUDES}"))
    message(FATAL_ERROR "Directory does not exist: ${PLATFORM_INCLUDES}")
endif()
if(NOT (EXISTS "${PLATFORM_LIBS}" AND IS_DIRECTORY "${PLATFORM_LIBS}"))
    message(FATAL_ERROR "Directory does not exist: ${PLATFORM_LIBS}")
endif()
if(NOT (EXISTS "${PLATFORM_BINS}" AND IS_DIRECTORY "${PLATFORM_BINS}"))
    message(FATAL_ERROR "Directory does not exist: ${PLATFORM_BINS}")
endif()

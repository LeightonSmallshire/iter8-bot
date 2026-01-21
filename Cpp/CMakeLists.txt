cmake_minimum_required(VERSION 3.20)
project(DiscordBot LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)

# ----------------------------------------

# Force static linking for standard libraries
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -static-libgcc -static-libstdc++")
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(DPP_BUILD_STATIC ON CACHE BOOL "" FORCE)
set(OPENSSL_USE_STATIC_LIBS TRUE)

# ----------------------------------------
# SQLite
# ----------------------------------------

add_library(sqlite3 STATIC
    ${CMAKE_SOURCE_DIR}/thirdparty/sqlite/sqlite3.c
)

target_include_directories(sqlite3 PUBLIC
    ${CMAKE_SOURCE_DIR}/thirdparty/sqlite
)

# ---------------------------------------
# Fetch spdlog
# ---------------------------------------

FetchContent_Declare(
    spdlog
    GIT_REPOSITORY https://github.com/gabime/spdlog.git
    GIT_TAG        v1.16.0      
)

FetchContent_MakeAvailable(spdlog)

# ---------------------------------------
# Fetch nlohmann json
# ---------------------------------------

FetchContent_Declare(
    nlohmann_json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG        v3.11.3
)

FetchContent_MakeAvailable(nlohmann_json)

# ---------------------------------------
# Fetch magic_enum
# ---------------------------------------

FetchContent_Declare(
    magic_enum
    GIT_REPOSITORY https://github.com/Neargye/magic_enum
    GIT_TAG        v0.9.7   
)

FetchContent_MakeAvailable(magic_enum)

# ---------------------------------------
# Fetch libarchive
# ---------------------------------------
set(ENABLE_NETTLE OFF CACHE BOOL "" FORCE)
set(ENABLE_OPENSSL ON CACHE BOOL "" FORCE)
set(ENABLE_LIBXML2 ON CACHE BOOL "" FORCE)
set(ENABLE_LZMA ON CACHE BOOL "" FORCE)
set(ENABLE_ZLIB ON CACHE BOOL "" FORCE)

# This stops libarchive from building bsdcat, bsdtar, etc., 
# which are causing your current linker errors.
set(ENABLE_TAR OFF CACHE BOOL "" FORCE)
set(ENABLE_CPIO OFF CACHE BOOL "" FORCE)
set(ENABLE_CAT OFF CACHE BOOL "" FORCE)
set(ENABLE_INSTALL OFF CACHE BOOL "" FORCE)
set(ENABLE_TEST OFF CACHE BOOL "" FORCE)
set(ENABLE_MBEDTLS OFF CACHE BOOL "" FORCE)
set(ENABLE_NETTLE OFF CACHE BOOL "" FORCE)
set(ENABLE_UNZIP OFF CACHE BOOL "" FORCE)

set(CMAKE_FIND_LIBRARY_SUFFIXES ".a" CACHE INTERNAL "")

FetchContent_Declare(libarchive
    GIT_REPOSITORY https://github.com/libarchive/libarchive.git
    GIT_TAG        v3.7.4     # or whatever version you want
)

FetchContent_MakeAvailable(libarchive)

# -------------------------
# stb
# -------------------------

FetchContent_Declare(
    stb
    GIT_REPOSITORY https://github.com/nothings/stb.git
    GIT_TAG        master
)
FetchContent_MakeAvailable(stb)

add_library(stb INTERFACE)
target_include_directories(stb INTERFACE ${stb_SOURCE_DIR})

# ---------------------------------------
# Fetch DPP
# ---------------------------------------

set(DPP_BUILD_TEST OFF CACHE BOOL "Don't build DPP test programs" FORCE)
set(DPP_NO_VCPKG ON CACHE BOOL "Don't use DPP's internal vcpkg" FORCE)
set(BUILD_VOICE_SUPPORT OFF CACHE BOOL "Don't use VOIP" FORCE)

FetchContent_Declare(
    dpp
    GIT_REPOSITORY https://github.com/brainboxdotcc/DPP
    GIT_TAG        bef3e2be44f0cb11f7756da541a9e25df766a06b
)

FetchContent_MakeAvailable(dpp)

# -------------------------------
# Add your Discord bot executable
# -------------------------------

file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS "${CMAKE_SOURCE_DIR}/src/*.cpp")
add_executable(discord_bot ${SOURCES})

target_include_directories(discord_bot PRIVATE src)
target_include_directories(discord_bot PUBLIC ${CMAKE_SOURCE_DIR}/thirdparty )

target_link_libraries(discord_bot PRIVATE
    sqlite3
    spdlog::spdlog
    nlohmann_json::nlohmann_json
    magic_enum::magic_enum
    stb
    archive_static
    dpp
    # System libs - order matters!
    ssl
    crypto
    xml2
    lzma
    z
)

target_compile_definitions(discord_bot PRIVATE LIBARCHIVE_STATIC)

if (WIN32)
    set(THIRDPARTY_DLLS
        "${CMAKE_SOURCE_DIR}/thirdparty/openssl/libcrypto-1_1-x64.dll"
        "${CMAKE_SOURCE_DIR}/thirdparty/openssl/libssl-1_1-x64.dll"
        "${CMAKE_SOURCE_DIR}/thirdparty/opus/opus.dll"
        "${CMAKE_SOURCE_DIR}/thirdparty/zlib/zlib1.dll"
    )

    add_custom_command(TARGET discord_bot POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E make_directory
                $<TARGET_FILE_DIR:discord_bot>
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
                ${THIRDPARTY_DLLS}
                $<TARGET_FILE_DIR:discord_bot>
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
                $<TARGET_RUNTIME_DLLS:discord_bot>
                $<TARGET_FILE_DIR:discord_bot>
        COMMAND_EXPAND_LISTS
    )
endif()

add_custom_command(
    TARGET discord_bot
    POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory
            "${CMAKE_CURRENT_SOURCE_DIR}/data"
            "$<TARGET_FILE_DIR:discord_bot>/data"
    COMMENT "Copying data directory to output folder"
)

# 1. Install the bot binary
install(TARGETS discord_bot DESTINATION .)

# 2. Install the data directory (Redistributable assets)
install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/data" DESTINATION .)

# 3. If DPP or libarchive are built as shared libraries, install them too
# This ensures any .so files needed are bundled in the output
install(TARGETS dpp spdlog archive_static DESTINATION .)

# install(CODE [[
#     file(GET_RUNTIME_DEPENDENCIES
#         EXECUTABLES $<TARGET_FILE:discord_bot>
#         RESOLVED_DEPENDENCIES_VAR _resolved_deps
#         UNRESOLVED_DEPENDENCIES_VAR _unresolved_deps
#         # ONLY exclude the specific libraries that cause version conflicts
#         PRE_EXCLUDE_REGEXES 
#             "libc\\.so.*"
#             "libm\\.so.*"
#             "libdl\\.so.*"
#             "librt\\.so.*"
#             "libpthread\\.so.*"
#             "libgcc_s\\.so.*"
#             "libstdc\\+\\+\\.so.*"
#             "ld-linux-x86-64\\.so.*"
#     )
#
#     foreach(_file ${_resolved_deps})
#         # 1. Resolve the symlink to get the actual physical file
#         get_filename_component(_real_file "${_file}" REALPATH)
#
#         # 2. Get the filename the bot expects (e.g., liblzma.so.5)
#         get_filename_component(_name_expected "${_file}" NAME)
#
#         # 3. Log the mapping for debugging 
#         message(STATUS "Installing dependency: \"${_name_expected}\"")
#         message(STATUS "  From: \"${_file}\"")
#         message(STATUS "  Real path: \"${_real_file}\"")
#
#         # 4. Corrected Install Command
#         file(INSTALL
#             DESTINATION "${CMAKE_INSTALL_PREFIX}"
#             TYPE PROGRAM
#             RENAME "${_name_expected}"
#             FILES "${_real_file}"
#         )
#     endforeach()
#
#     # Log unresolved deps to see if anything critical (like liblzma) failed to resolve
#     foreach(_unresolved ${_unresolved_deps})
#         message(WARNING "Unresolved dependency: ${_unresolved}")
#     endforeach()
# ]])

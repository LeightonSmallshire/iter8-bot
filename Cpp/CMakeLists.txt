cmake_minimum_required(VERSION 3.20)
project(DiscordBot LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)

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
set(ENABLE_TEST OFF CACHE BOOL "" FORCE)
set(ENABLE_INSTALL OFF CACHE BOOL "" FORCE)

FetchContent_Declare(libarchive
    GIT_REPOSITORY https://github.com/libarchive/libarchive.git
    GIT_TAG        v3.7.4     # or whatever version you want
)

FetchContent_MakeAvailable(libarchive)

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
    magic_enum::magic_enum
    archive_static
    dpp
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
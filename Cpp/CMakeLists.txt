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
set(ENABLE_TEST OFF CACHE BOOL "" FORCE)
set(ENABLE_INSTALL OFF CACHE BOOL "" FORCE)

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

# -------------------------------
# Add your Discord bot executable
# -------------------------------

file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS "${CMAKE_SOURCE_DIR}/src/*.cpp")
add_executable(discord_bot ${SOURCES})

target_include_directories(discord_bot PRIVATE src)
target_include_directories(discord_bot PUBLIC ${CMAKE_SOURCE_DIR}/thirdparty )
target_include_directories(discord_bot PUBLIC "${CMAKE_SOURCE_DIR}/thirdparty/dpp/include/dpp-10.1" )

target_link_libraries(discord_bot PRIVATE
    sqlite3
    spdlog::spdlog
    nlohmann_json::nlohmann_json
    magic_enum::magic_enum
    stb
    archive_static
)

target_compile_definitions(discord_bot PRIVATE LIBARCHIVE_STATIC)

set(DPP_CFG_DIR "$<CONFIG>-$<PLATFORM_ID>-${CMAKE_SYSTEM_PROCESSOR}")

set(DPP_BIN_DIR "${CMAKE_SOURCE_DIR}/thirdparty/dpp/bin/${DPP_CFG_DIR}")
set(DPP_LIB_DIR "${CMAKE_SOURCE_DIR}/thirdparty/dpp/lib/${DPP_CFG_DIR}")

target_link_directories(discord_bot PRIVATE
    "${DPP_LIB_DIR}"
)

target_link_libraries(discord_bot PRIVATE
    dpp
)

if (WIN32)
    set(THIRDPARTY_DLLS
        "${CMAKE_SOURCE_DIR}/thirdparty/openssl/libcrypto-1_1-x64.dll"
        "${CMAKE_SOURCE_DIR}/thirdparty/openssl/libssl-1_1-x64.dll"
        "${CMAKE_SOURCE_DIR}/thirdparty/opus/opus.dll"
        "${CMAKE_SOURCE_DIR}/thirdparty/zlib/zlib1.dll"
        "${DPP_BIN_DIR}/dpp.dll"
    )

    add_custom_command(TARGET discord_bot POST_BUILD
      COMMAND ${CMAKE_COMMAND} -E make_directory
              "$<TARGET_FILE_DIR:discord_bot>"

      COMMAND ${CMAKE_COMMAND} -E copy_if_different
              ${THIRDPARTY_DLLS}
              "$<TARGET_FILE_DIR:discord_bot>"

      COMMAND ${CMAKE_COMMAND} -E $<$<BOOL:$<TARGET_RUNTIME_DLLS:discord_bot>>:copy_if_different>
              $<TARGET_RUNTIME_DLLS:discord_bot>
              "$<TARGET_FILE_DIR:discord_bot>"

      COMMAND_EXPAND_LISTS
    )
elseif(UNIX AND NOT APPLE)
    set(THIRDPARTY_DLLS
        "${DPP_BIN_DIR}/libdpp.so"
    )

    add_custom_command(TARGET discord_bot POST_BUILD
      COMMAND ${CMAKE_COMMAND} -E make_directory
              "$<TARGET_FILE_DIR:discord_bot>"

      COMMAND ${CMAKE_COMMAND} -E copy_if_different
              ${THIRDPARTY_DLLS}
              "$<TARGET_FILE_DIR:discord_bot>"

      COMMAND ${CMAKE_COMMAND} -E $<$<BOOL:$<TARGET_RUNTIME_DLLS:discord_bot>>:copy_if_different>
              $<TARGET_RUNTIME_DLLS:discord_bot>
              "$<TARGET_FILE_DIR:discord_bot>"

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
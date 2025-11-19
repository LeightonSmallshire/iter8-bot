cmake_minimum_required(VERSION 3.20)
project(DiscordBot LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# -----------------------------
# Magical logic for selecting from prebuilt binaries (64-bit only)
# -----------------------------

if (WIN32)
    if (CMAKE_BUILD_TYPE STREQUAL "Debug")
        include_directories(thirdparty/libdpp-10.1.3-win64-debug/include/dpp-10.1)
        link_directories(thirdparty/libdpp-10.1.3-win64-debug/bin)
    else ()
        include_directories(thirdparty/libdpp-10.1.3-win64-release/include/dpp-10.1)
        link_directories(thirdparty/libdpp-10.1.3-win64-release/bin)
    endif ()
elseif (UNIX)
    include_directories(thirdparty/libdpp-10.1.3-linux-x64/usr/include)
    link_directories(thirdparty/libdpp-10.1.3-linux-x64/usr/lib)
else ()
    message(FATAL_ERROR "Unsupported OS")
endif ()

# -----------------------------
# Add your Discord bot executable
# -----------------------------

file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS "${CMAKE_SOURCE_DIR}/src/*.cpp")
add_executable(discord_bot ${SOURCES})
target_include_directories(discord_bot PRIVATE src)
target_link_libraries(discord_bot PRIVATE dpp)

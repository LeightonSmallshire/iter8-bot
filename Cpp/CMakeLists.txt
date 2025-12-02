cmake_minimum_required(VERSION 3.20)
project(DiscordBot LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# -------------------------------
# Add your Discord bot executable
# -------------------------------

file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS "${CMAKE_SOURCE_DIR}/src/*.cpp")
add_executable(discord_bot ${SOURCES})
target_include_directories(discord_bot PRIVATE src)
target_include_directories(discord_bot PUBLIC
    ${CMAKE_SOURCE_DIR}/thirdparty
)

# ----------------------------------------------------------------
# Magical logic for selecting from prebuilt binaries (64-bit only)
# ----------------------------------------------------------------

if (WIN32)
    if (CMAKE_BUILD_TYPE STREQUAL "Debug")
        target_include_directories(discord_bot PRIVATE thirdparty/libdpp-10.1.4-win64-debug/include/dpp-10.1)
        target_link_directories(discord_bot PRIVATE thirdparty/libdpp-10.1.4-win64-debug/lib/dpp-10.1)
        target_link_libraries(discord_bot PRIVATE dpp)
        
        add_custom_command(TARGET discord_bot POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_directory
            "${CMAKE_SOURCE_DIR}/thirdparty/libdpp-10.1.4-win64-debug/bin"
            $<TARGET_FILE_DIR:discord_bot>)
    else ()
        target_include_directories(discord_bot PRIVATE thirdparty/libdpp-10.1.4-win64-release/include/dpp-10.1)
        target_link_directories(discord_bot PRIVATE thirdparty/libdpp-10.1.4-win64-release/lib/dpp-10.1)
        target_link_libraries(discord_bot PRIVATE dpp)
        
        add_custom_command(TARGET discord_bot POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_directory
            "${CMAKE_SOURCE_DIR}/thirdparty/libdpp-10.1.4-win64-release/bin"
            $<TARGET_FILE_DIR:discord_bot>)
    endif ()
elseif (UNIX)
    target_include_directories(discord_bot PRIVATE thirdparty/libdpp-10.1.4-linux-x64/usr/include)
    target_link_directories(discord_bot PRIVATE thirdparty/libdpp-10.1.4-linux-x64/usr/lib)
    target_link_libraries(discord_bot PRIVATE dpp)
else ()
    message(FATAL_ERROR "Unsupported OS")
endif ()

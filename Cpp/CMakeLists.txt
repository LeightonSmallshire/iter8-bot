cmake_minimum_required(VERSION 3.20)
project(DiscordBot LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)
include(cmake/sqlite.cmake)
include(cmake/spdlog.cmake)
include(cmake/magic_enum.cmake)
include(cmake/git_hash.cmake)
include(cmake/platform_string.cmake)

# -------------------------------
# Discord bot executable
# -------------------------------

file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS "${CMAKE_SOURCE_DIR}/src/*.cpp")
add_executable(discord_bot ${SOURCES})
target_include_directories(discord_bot PRIVATE src)

target_compile_definitions(discord_bot PRIVATE GIT_VERSION=\"${GIT_DESCRIBE}\")
# target_include_directories(discord_bot PUBLIC ${CMAKE_SOURCE_DIR}/thirdparty)
target_include_directories(discord_bot PUBLIC ${}/)

target_link_libraries(discord_bot PRIVATE sqlite3)
target_link_libraries(discord_bot PRIVATE spdlog::spdlog $<$<BOOL:${MINGW}>:ws2_32>)
target_link_libraries(discord_bot PRIVATE magic_enum::magic_enum)

# Platform-specific directories, copy dlls
target_include_directories(discord_bot PRIVATE ${PLATFORM_INCLUDES})
target_link_directories(discord_bot PRIVATE ${PLATFORM_LIBS})
add_custom_command(TARGET discord_bot POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory ${PLATFORM_BINS} $<TARGET_FILE_DIR:discord_bot>)

target_link_libraries(discord_bot PRIVATE dpp)

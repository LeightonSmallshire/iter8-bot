cmake_minimum_required(VERSION 3.20)
project(DiscordBot LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# -----------------------------
# Add your Discord bot executable
# -----------------------------

file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS "${CMAKE_SOURCE_DIR}/src/*.cpp")
add_executable(${CMAKE_PROJECT_NAME} ${SOURCES})
target_include_directories(${CMAKE_PROJECT_NAME} PRIVATE src)
target_link_libraries(${CMAKE_PROJECT_NAME} PRIVATE dpp)

# -----------------------------
# Magical logic for selecting from prebuilt binaries (64-bit only)
# -----------------------------

if (WIN32)
    if (CMAKE_BUILD_TYPE STREQUAL "Release")
        set(LIBDPP_DIRECTORY "libdpp-10.1.3-win64-release")
    else()
        set(LIBDPP_DIRECTORY "libdpp-10.1.3-win64-debug")
    endif()

    target_include_directories( ${CMAKE_PROJECT_NAME} PRIVATE
        ${CMAKE_SOURCE_DIR}/thirdparty/${LIBDPP_DIRECTORY}/include/dpp-10.1)

    target_link_directories( ${CMAKE_PROJECT_NAME} PRIVATE
        ${CMAKE_SOURCE_DIR}/thirdparty/${LIBDPP_DIRECTORY}/lib/dpp-10.1)

    add_custom_command(TARGET ${CMAKE_PROJECT_NAME} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_directory
            "${CMAKE_SOURCE_DIR}/thirdparty/${LIBDPP_DIRECTORY}/bin"
            $<TARGET_FILE_DIR:${CMAKE_PROJECT_NAME}>
    )

elseif (UNIX)
    include_directories(thirdparty/libdpp-10.1.3-linux-x64/usr/include)
    link_directories(thirdparty/libdpp-10.1.3-linux-x64/usr/lib)
else ()
    message(FATAL_ERROR "Unsupported OS")
endif ()

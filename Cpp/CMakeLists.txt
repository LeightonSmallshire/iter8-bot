cmake_minimum_required(VERSION 3.20)
project(DiscordBot LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

cmake_policy(SET CMP0135 NEW) # DOWNLOAD_EXTRACT_TIMESTAMP behaviour

include(FetchContent)

# set(CMAKE_FIND_LIBRARY_SUFFIXES ".so;.a")

# ----------------------------------------

# Force static linking for standard libraries
# set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -static-libgcc -static-libstdc++")
# set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
# set(DPP_BUILD_STATIC ON CACHE BOOL "" FORCE)
# set(OPENSSL_USE_STATIC_LIBS TRUE)


# ---------------------------------------

list(APPEND CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/cmake)

include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/sqlite3.cmake")
include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/spdlog.cmake")
include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/nlohmann_json.cmake")
include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/magic_enum.cmake")
include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/libarchive.cmake")
include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/stb.cmake")

# WIP
# include("dpp.cmake")
find_package(DPP REQUIRED)


# -------------------------------
# Add your Discord bot executable
# -------------------------------

file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS "${CMAKE_SOURCE_DIR}/src/*.cpp")
add_executable(discord_bot ${SOURCES})

target_include_directories(discord_bot PRIVATE src)
target_include_directories(discord_bot PUBLIC ${CMAKE_SOURCE_DIR}/thirdparty ${DPP_INCLUDE_DIR} )

target_link_libraries(discord_bot PRIVATE
    sqlite3
    spdlog::spdlog
    nlohmann_json::nlohmann_json
    magic_enum::magic_enum
    stb
    archive
    dpp::dpp
    # System libs - order matters!
    ssl
    crypto
    xml2
    lzma
    z
)


# This tells the executable to look in its own directory for libraries
set(CMAKE_INSTALL_RPATH "$ORIGIN")
set(CMAKE_BUILD_WITH_INSTALL_RPATH TRUE)




# target_compile_definitions(discord_bot PRIVATE LIBARCHIVE_STATIC)

# if (WIN32)
#     set(THIRDPARTY_DLLS
#         "${CMAKE_SOURCE_DIR}/thirdparty/openssl/libcrypto-1_1-x64.dll"
#         "${CMAKE_SOURCE_DIR}/thirdparty/openssl/libssl-1_1-x64.dll"
#         "${CMAKE_SOURCE_DIR}/thirdparty/opus/opus.dll"
#         "${CMAKE_SOURCE_DIR}/thirdparty/zlib/zlib1.dll"
#     )

#     add_custom_command(TARGET discord_bot POST_BUILD
#         COMMAND ${CMAKE_COMMAND} -E make_directory
#                 $<TARGET_FILE_DIR:discord_bot>
#         COMMAND ${CMAKE_COMMAND} -E copy_if_different
#                 ${THIRDPARTY_DLLS}
#                 $<TARGET_FILE_DIR:discord_bot>
#         COMMAND ${CMAKE_COMMAND} -E copy_if_different
#                 $<TARGET_RUNTIME_DLLS:discord_bot>
#                 $<TARGET_FILE_DIR:discord_bot>
#         COMMAND_EXPAND_LISTS
#     )
# endif()


add_custom_command(
    TARGET discord_bot
    POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory
            ${CMAKE_CURRENT_SOURCE_DIR}/data
            $<TARGET_FILE_DIR:discord_bot>/data
    COMMENT "Copying data directory to output folder"
)


add_custom_command(TARGET discord_bot POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
    $<TARGET_FILE:dpp::dpp>
    $<TARGET_FILE_DIR:discord_bot>
    COMMENT "Copying shared libraries to output folder"
)


# Runtime Path: Since you are using dynamic libraries (.so), you'll need to tell the OS where to find them at runtime. Add this to your CMakeLists.txt to bake the path into the executable:
# set_target_properties(discord_bot PROPERTIES INSTALL_RPATH "$ORIGIN/../thirdparty/dpp/lib")

# 1. Install the bot binary
install(TARGETS discord_bot DESTINATION .)

# 2. Install the data directory (Redistributable assets)
install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/data" DESTINATION .)

# 3. If DPP or libarchive are built as shared libraries, install them too
# This ensures any .so files needed are bundled in the output
# install(TARGETS spdlog archive_static DESTINATION .)
# TODO  ${DPP_LIBRARIES} 

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

block()
    FetchContent_Declare(
        sqlite3
        URL      https://sqlite.org/2026/sqlite-amalgamation-3510200.zip
        URL_HASH SHA3_256=9a9dd4eef7a97809bfacd84a7db5080a5c0eff7aaf1fc1aca20a6dc9a0c26f96
    )
    FetchContent_GetProperties(sqlite3)
    FetchContent_MakeAvailable(sqlite3)

    add_library(sqlite3 STATIC "${sqlite3_SOURCE_DIR}/sqlite3.c" )
    target_include_directories(sqlite3 PUBLIC "${sqlite3_SOURCE_DIR}" )

    if(UNIX AND NOT APPLE)
            target_link_libraries(sqlite3 PRIVATE pthread dl m)
    endif()
endblock()

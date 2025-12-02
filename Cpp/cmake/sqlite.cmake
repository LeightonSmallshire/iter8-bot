
add_library(sqlite3 STATIC
	${CMAKE_SOURCE_DIR}/thirdparty/sqlite/sqlite3.c
)
target_include_directories(sqlite3 PUBLIC
	${CMAKE_SOURCE_DIR}/thirdparty/sqlite
)

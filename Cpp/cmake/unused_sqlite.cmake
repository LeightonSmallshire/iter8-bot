
# FetchContent_Declare(
#     sqlite
#     GIT_REPOSITORY "https://https://github.com/sqlite/sqlite.git"
#     GIT_TAG        "version-3.44.4"
# )
# FetchContent_MakeAvailable(sqlite)

FetchContent_Declare(sqlite3 
	GIT_REPOSITORY https://github.com/sjinks/sqlite3-cmake
	GIT_TAG v3.49.1
)
FetchContent_MakeAvailable(sqlite3)

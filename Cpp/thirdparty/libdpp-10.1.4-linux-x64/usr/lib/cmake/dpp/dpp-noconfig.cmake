#----------------------------------------------------------------
# Generated CMake target import file.
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "dpp::dpp" for configuration ""
set_property(TARGET dpp::dpp APPEND PROPERTY IMPORTED_CONFIGURATIONS NOCONFIG)
set_target_properties(dpp::dpp PROPERTIES
  IMPORTED_LOCATION_NOCONFIG "${_IMPORT_PREFIX}/lib/libdpp.so.10.1.4"
  IMPORTED_SONAME_NOCONFIG "libdpp.so.10.1.4"
  )

list(APPEND _cmake_import_check_targets dpp::dpp )
list(APPEND _cmake_import_check_files_for_dpp::dpp "${_IMPORT_PREFIX}/lib/libdpp.so.10.1.4" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)

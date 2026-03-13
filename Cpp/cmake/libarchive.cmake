block()
    set(ENABLE_NETTLE  OFF CACHE BOOL "" FORCE)
    set(ENABLE_OPENSSL  ON CACHE BOOL "" FORCE)
    set(ENABLE_LIBXML2  ON CACHE BOOL "" FORCE)
    set(ENABLE_LZMA     ON CACHE BOOL "" FORCE)
    set(ENABLE_ZLIB     ON CACHE BOOL "" FORCE)

    # This stops libarchive from building bsdcat, bsdtar, etc.
    set(ENABLE_TAR     OFF CACHE BOOL "" FORCE)
    set(ENABLE_CPIO    OFF CACHE BOOL "" FORCE)
    set(ENABLE_CAT     OFF CACHE BOOL "" FORCE)
    set(ENABLE_INSTALL OFF CACHE BOOL "" FORCE)
    set(ENABLE_TEST    OFF CACHE BOOL "" FORCE)
    set(ENABLE_MBEDTLS OFF CACHE BOOL "" FORCE)
    set(ENABLE_NETTLE  OFF CACHE BOOL "" FORCE)
    set(ENABLE_UNZIP   OFF CACHE BOOL "" FORCE)

    FetchContent_Declare(
        libarchive
        URL      https://github.com/libarchive/libarchive/archive/refs/tags/v3.8.5.zip
        URL_HASH SHA256=8c048408d66fd7abdc0ac93b89fd922210ea8c07312f0c667cd505dcc92502b7
    )
    FetchContent_MakeAvailable(libarchive)
endblock()

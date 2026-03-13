block()
    FetchContent_Declare(
        magic_enum
        URL      https://github.com/Neargye/magic_enum/archive/refs/tags/v0.9.7.zip
        URL_HASH SHA256=e293afdaf4d5918bc145903bccff06d28b3ed437f1ac8414ace9e8a769a9e470
    )
    FetchContent_MakeAvailable(magic_enum)
endblock()

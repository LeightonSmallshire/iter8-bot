block()
    FetchContent_Declare(
        stb
        URL      https://github.com/nothings/stb/archive/f1c79c0.zip
        URL_HASH SHA256=461ed3e66abb68187c5880554b60ae1e9e0a3112324c93d2453c6a2e65369120
    )
    FetchContent_MakeAvailable(stb)
    
    add_library(stb INTERFACE)
    target_include_directories(stb INTERFACE ${stb_SOURCE_DIR})
endblock()

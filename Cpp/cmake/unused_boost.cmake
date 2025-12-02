set(BOOST_INCLUDE_LIBRARIES
    math
    filesystem
    system
    program_options
    units
    asio
    ssl
    pfr
)

set(BOOST_ENABLE_CMAKE ON)

FetchContent_Declare(
    Boost
    GIT_REPOSITORY https://github.com/boostorg/boost.git
    GIT_TAG boost-1.87.0 
    GIT_SHALLOW TRUE
    GIT_PROGRESS TRUE )

FetchContent_MakeAvailable(Boost)

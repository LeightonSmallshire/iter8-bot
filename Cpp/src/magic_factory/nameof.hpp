#pragma once
#include <string_view>

namespace
{
    namespace detail
    {
        template <typename T>
        constexpr std::string_view raw_type_name()
        {
#if defined(__clang__) || defined(__GNUC__)
            return __PRETTY_FUNCTION__;
#elif defined(_MSC_VER)
            return __FUNCSIG__;
#else
#error Unsupported compiler
#endif
        }

        constexpr std::string_view extract(std::string_view sv,
                                           std::string_view prefix,
                                           std::string_view suffix)
        {

            auto start = sv.find(prefix);
            if (start == std::string_view::npos)
                return {};

            start += prefix.size();
            auto end = sv.rfind(suffix);
            if (end == std::string_view::npos || end <= start)
                return {};

            return sv.substr(start, end - start);
        }
    }
} // namespace detail

template <typename T>
constexpr std::string_view nameof()
{
#if defined(__clang__) || defined(__GNUC__)
    // Example GCC/Clang __PRETTY_FUNCTION__:
    // "constexpr std::string_view detail::raw_type_name() [with T = Foo]"
    constexpr std::string_view prefix = "T = ";
    constexpr std::string_view suffix = "]";
    return detail::extract(detail::raw_type_name<T>(), prefix, suffix);

#elif defined(_MSC_VER)
    // Example MSVC __FUNCSIG__:
    // "consteval std::string_view __cdecl detail::raw_type_name<struct Foo>(void)"
    // TODO: auto get prefix & suffix using a dummy struct / class
    constexpr std::string_view prefix = "raw_type_name<class ";
    constexpr std::string_view suffix = ">(void)";
    return detail::extract(detail::raw_type_name<T>(), prefix, suffix);

#endif
}

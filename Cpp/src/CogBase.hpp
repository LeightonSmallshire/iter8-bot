#pragma once
#include <string>
#include <map>
#include <functional>

namespace cogs
{
    class Cog
    {
        explicit Cog() = default;
        Cog(Cog &&) = delete;
        Cog(Cog const &) = delete;
        Cog &operator=(Cog &&) = delete;
        Cog &operator=(Cog const &) = delete;


    public:
    }

}

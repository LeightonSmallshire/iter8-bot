#pragma once

#include "nameof.hpp"

#include <iostream>
#include <memory>
#include <string>
#include <unordered_map>

// https://coliru.stacked-crooked.com/a/11473a649e402831

namespace build
{
    template <class Base, class... Args>
    class Factory
    {
    public:
        template <class... T>
        static std::unique_ptr<Base> make(std::string const& s, T &&...args)
        {
            return data().at(s)(std::forward<T>(args)...);
        }

        template <class T>
        struct Registrar : Base
        {
            friend T;

            static bool registerT()
            {
                auto const name = nameof<T>();
                Factory::data()[std::string{ name }] = [](Args... args) -> std::unique_ptr<Base>
                    {
                        return std::make_unique<T>(std::forward<Args>(args)...);
                    };
                return true;
            }
            //static inline bool registered = registerT();
            static bool registered;

        private:
            Registrar() : Base(Key{}) { (void)registered; }
        };

        friend Base;

    private:
        class Key
        {
            Key() {};
            template <class T>
            friend struct Registrar;
        };
        using FuncType = std::unique_ptr<Base>(*)(Args...);
        Factory() = default;

        static auto& data()
        {
            static std::unordered_map<std::string, FuncType> s;
            return s;
        }
    };

    template <class Base, class... Args>
    template <class T>
    bool Factory<Base, Args...>::Registrar<T>::registered = registerT();

} // namespace build

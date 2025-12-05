#pragma once
#include "magic_factory/nameof.hpp"

#include <functional>
#include <map>
#include <string>

//namespace cogs
//{
//
//    class CogBase {
//    public:
//
//    };
//
//
//
//    class CogRegistry
//    {
//        explicit CogRegistry() = default;
//        CogRegistry(CogRegistry&&) = delete;
//        CogRegistry(CogRegistry const&) = delete;
//        CogRegistry& operator=(CogRegistry&&) = delete;
//        CogRegistry& operator=(CogRegistry const&) = delete;
//
//        using Constructor = std::function<>;
//        std::map<std::string, >
//        
//        static CogRegistry& instance()
//        {
//            static auto inst = CogRegistry();
//            return inst;
//        }
//
//        template<class T>
//        void registerT() {
//            auto const name = nameof<T>();
//
//        }
//
//    public:
//        void registerCog() {
//
//        }
//
//
//        template<class T>
//        class Register : CogBase {
//            explicit Register() :CogB {}
//        };
//    };
//}

#pragma once

#include <spdlog/spdlog.h>
#include <spdlog/fmt/ostr.h>

namespace iter8::db
{
	class Connection;
}

namespace iter8::log
{
	namespace detail
	{
		std::shared_ptr< spdlog::logger >& GetLogger();
	}

	void Init( iter8::db::Connection& db );

	template < typename... Args >
	void Trace( spdlog::format_string_t< Args... > fmt, Args&&... args )
	{
		detail::GetLogger()->trace( fmt, std::forward< Args >( args )... );
	}

	template < typename... Args >
	void Info( spdlog::format_string_t< Args... > fmt, Args&&... args )
	{
		detail::GetLogger()->info( fmt, std::forward< Args >( args )... );
	}

	template < typename... Args >
	void Warn( spdlog::format_string_t< Args... > fmt, Args&&... args )
	{
		detail::GetLogger()->warn( fmt, std::forward< Args >( args )... );
	}

	template < typename... Args >
	void Error( spdlog::format_string_t< Args... > fmt, Args&&... args )
	{
		detail::GetLogger()->error( fmt, std::forward< Args >( args )... );
	}

	template < typename... Args >
	void Critical( spdlog::format_string_t< Args... > fmt, Args&&... args )
	{
		detail::GetLogger()->critical( fmt, std::forward< Args >( args )... );
	}
} // namespace iter8::log
#pragma once

#include "Common.h"

#include "dpp/dpp.h"

#include <optional>

namespace iter8
{
	struct CommandArgumentDefinition
	{
		dpp::command_option_type type;
		std::string name;
		std::string description{};
		bool required{};
	};

	struct CommandDefinition
	{
		std::string name;
		std::string description{};
		std::vector< CommandArgumentDefinition > parameters;
	};

	template < typename T >
	std::optional< T > GetParameter( dpp::slashcommand_t const& e, std::string const& param )
	{
		auto opt = e.get_parameter( param );
		if ( std::holds_alternative< std::monostate >( opt ) )
			return std::nullopt;

		return std::get< T >( opt );
	}

	template < typename T >
	concept SlashCommandHandler = Callable< T, dpp::task< void >, dpp::slashcommand_t const >;

	template < typename T, typename event_t >
	concept ListenerHandler = Callable< T, dpp::task< void >, event_t const& >;

} // namespace iter8
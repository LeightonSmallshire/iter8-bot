#pragma once

#include "Common.h"

#include "dpp/dpp.h"

#include <optional>

namespace iter8
{
	template < typename T >
	concept SlashCommandHandler = Callable< T, dpp::task< void >, dpp::slashcommand_t const& >;

	using AutocompleteHandler = std::function< dpp::task< void >( dpp::autocomplete_t const&, dpp::command_option const& ) >;

	template < typename T, typename event_t >
	concept ListenerHandler = Callable< T, dpp::task< void >, event_t const& >;

	struct CommandArgumentDefinition
	{
		dpp::command_option_type type;
		std::string name;
		std::string description{};
		bool required{};
		AutocompleteHandler autocomplete{};
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

} // namespace iter8
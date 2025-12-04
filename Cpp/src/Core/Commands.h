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

	namespace detail
	{
		inline dpp::guild_member* FindGuildMember(dpp::snowflake const guild_id, dpp::snowflake const user_id)
		{
			using namespace dpp;
			guild* g = find_guild( guild_id );
			if ( g )
			{
				auto gm = g->members.find( user_id );
				if ( gm != g->members.end() )
				{
					return &gm->second;
				}
			}

			return nullptr;
		}
	}

	template < typename T >
	std::optional< T > GetParameter( dpp::slashcommand_t const& e, std::string const& param )
	{
		auto opt = e.get_parameter( param );
		if ( std::holds_alternative< std::monostate >( opt ) )
			return std::nullopt;

		if ( auto value = std::get_if< T >( &opt ) )
			return *value;

		return std::nullopt;
	}

	inline dpp::task< dpp::guild_member > GetMember( dpp::cluster& bot, dpp::snowflake id )
	{
		if ( auto member = detail::FindGuildMember( Guilds::Default, id ) )
			co_return *member;

		auto result = co_await bot.co_guild_get_member( Guilds::Default, id );
		co_return std::get< dpp::guild_member >( result.value );
	}

	inline dpp::task< dpp::user_identified > GetUser( dpp::cluster& bot, dpp::snowflake id )
	{
		if ( auto user = dpp::find_user( id ) )
			co_return *user;

		auto result = co_await bot.co_user_get( id );
		co_return std::get< dpp::user_identified >( result.value );
	}

} // namespace iter8
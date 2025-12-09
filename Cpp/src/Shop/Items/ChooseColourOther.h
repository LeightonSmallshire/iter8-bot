#pragma once

#include "Core/Discord.h"
#include "Shop/Item.h"

namespace iter8::shop
{
	class ChooseColourOther : public Handler
	{
	public:
		ChooseColourOther( db::Connection& db )
			: Handler( db )
		{}

		dpp::task< void > HandlePurchase( dpp::interaction_create_t& event, std::map< std::string, std::any > const& params ) override
		{
			if ( not event.owner )
				co_return;

			auto& bot = *event.owner;

			auto user = std::any_cast< dpp::snowflake >( params.at( "user" ) );
			auto colour = std::any_cast< std::uint32_t >( params.at( "colour" ) );

			auto result = co_await bot.co_roles_get( event.command.guild_id );
			auto roles = std::get< dpp::role_map >( result.value );

			auto role_id = dpp::snowflake{};

			auto it = std::ranges::find_if( roles, [ & ]( auto const& role ) { return role.second.name == event.command.usr.username; } );
			if (it != roles.end())
			{
				auto& role = it->second;
				role.set_colour( colour );
				co_await bot.co_role_edit( role );

				role_id = it->first;
			}
			else
			{
				dpp::role new_role{};
				new_role.guild_id = event.command.guild_id;
				new_role.name = event.command.usr.username;
				new_role.colour = colour;
				auto result = co_await bot.co_role_create( new_role );

				auto created = std::get< dpp::role >( result.value );
				role_id = created.id;
			}

			co_await bot.co_guild_member_add_role( event.command.guild_id, user, role_id );
		}

		std::vector< dpp::component > GetInputHandlers()
		{
			return {};
		}
	};
} // namespace iter8::shop
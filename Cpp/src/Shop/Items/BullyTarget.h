#pragma once

#include "Core/Discord.h"
#include "Shop/Item.h"

namespace iter8::shop
{
	class BullyTarget : public Handler
	{
	public:
		BullyTarget( db::Connection& db )
			: Handler( db )
		{}

		dpp::task< void > HandlePurchase( dpp::interaction_create_t& event, std::map< std::string, std::any > const& params ) override
		{
			if ( not event.owner )
				co_return;

			auto& bot = *event.owner;

			auto user = std::any_cast< dpp::snowflake >( params.at( "user" ) );

			auto admin = co_await GetRole( bot, event.command.guild_id, Roles::Admin );

			if (admin.get_members().contains(user))
			{
				co_await event.co_follow_up( "Can't make the admin the bully target" );
				co_return;
			}

			auto bully_target = co_await GetRole( bot, event.command.guild_id, Roles::BullyTarget );
			for ( auto&& [ target, _ ] : bully_target.get_members() )
				co_await bot.co_guild_member_remove_role( event.command.guild_id, target, Roles::BullyTarget );

			co_await bot.co_guild_member_add_role( event.command.guild_id, user, Roles::BullyTarget );

			co_await event.co_follow_up( std::format( "<@{}> made <@{}> is the new bully target. GET THEM!", event.command.usr.id.str(), user.str() ) );
		}

		std::vector< dpp::component > GetInputHandlers()
		{
			return {};
		}
	};
} // namespace iter8::shop
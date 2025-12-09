#pragma once

#include "Core/Discord.h"
#include "Shop/Item.h"
#include "Utils/Rolls.h"

namespace iter8::shop
{
	class MakeAdmin : public Handler
	{
	public:
		MakeAdmin( db::Connection& db )
			: Handler( db )
		{}

		dpp::task< void > HandlePurchase( dpp::interaction_create_t& event, std::map< std::string, std::any > const& params ) override
		{
			if ( not event.owner )
				co_return;

			auto& bot = *event.owner;

			auto admin = co_await GetRole( bot, event.command.guild_id, Roles::Admin );
			for ( auto&& [ target, _ ] : admin.get_members() )
				co_await bot.co_guild_member_remove_role( event.command.guild_id, target, Roles::Admin );

			co_await bot.co_guild_member_add_role( event.command.guild_id, event.command.usr.id, Roles::Admin );

			co_await event.co_follow_up( std::format( "<@{}> made themselves the new admin! All hail your new overlord", event.command.usr.id.str() ) );

			auto bully_target = co_await GetRole( bot, event.command.guild_id, Roles::BullyTarget );
			if ( bully_target.get_members().contains( event.command.usr.id ) )
			{
				auto roll_table = co_await GetNonBotMembers( bot, event.command.guild_id );
				std::erase_if( roll_table, [ & ]( auto const& mem ) { return mem.user_id == event.command.usr.id; } );

				co_await roll::DoRoleRoll(
					event,
					Roles::BullyTarget,
					roll_table,
					"🎲 New admin was the bully target. Finding a new target...",
					roll::MakeResponsePair( "<@{}> is free! <@{}> is the new bully target. GET THEM!", "<@{}> is the new bully target. GET THEM!" ) );
			}
		}

		std::vector< dpp::component > GetInputHandlers()
		{
			return {};
		}
	};
} // namespace iter8::shop
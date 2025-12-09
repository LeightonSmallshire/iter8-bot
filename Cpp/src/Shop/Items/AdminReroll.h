#pragma once

#include "Core/Discord.h"
#include "Shop/Item.h"
#include "Utils/Rolls.h"

namespace iter8::shop
{
	class AdminReroll : public Handler
	{
	public:
		AdminReroll( db::Connection& db )
			: Handler( db )
		{}

		dpp::task< void > HandlePurchase( dpp::interaction_create_t& event, std::map< std::string, std::any > const& params ) override
		{
			if ( not event.owner )
				co_return;

			auto& bot = *event.owner;

			auto roll_table = co_await GetNonBotMembers( bot, event.command.guild_id );

			auto new_admin = co_await roll::DoRoleRoll(
				event,
				Roles::Admin,
				roll_table,
				std::format( "🚨 {} called for a reroll! 🚨", event.command.usr.get_mention() ),
				roll::MakeResponsePair( "<@{}> is dead. Long live <@{}>.", "Long live <@{}>." ) );

			auto bully_role = co_await GetRole( bot, event.command.guild_id, Roles::BullyTarget );
			auto bully_targets = bully_role.get_members();

			if ( bully_targets.contains( new_admin ) )
			{
				std::erase_if( roll_table, [ = ]( auto const& mem ) { return mem.user_id == new_admin; } );

				co_await roll::DoRoleRoll(
					event,
					Roles::BullyTarget,
					roll_table,
					"🎲 Admin landed on the bully target. Finding a new target...",
					roll::MakeResponsePair( "<@{}> is free! <@{}> is the new bully target. GET THEM!", "<@{}> is the new bully target. GET THEM!" ) );
			}
		}

		std::vector< dpp::component > GetInputHandlers()
		{
			return {};
		}
	};
} // namespace iter8::shop
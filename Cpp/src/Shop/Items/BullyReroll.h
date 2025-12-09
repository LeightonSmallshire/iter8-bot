#pragma once

#include "Core/Discord.h"
#include "Shop/Item.h"
#include "Utils/Rolls.h"

namespace iter8::shop
{
	class BullyReroll : public Handler
	{
	public:
		BullyReroll( db::Connection& db )
			: Handler( db )
		{}

		dpp::task< void > HandlePurchase( dpp::interaction_create_t& event, std::map< std::string, std::any > const& params ) override
		{
			if ( not event.owner )
				co_return;

			auto& bot = *event.owner;

			auto roll_table = co_await GetNonBotMembers( bot, event.command.guild_id );

			auto admins = ( co_await GetRole( bot, event.command.guild_id, Roles::Admin ) ).get_members();
			auto bully_targets = ( co_await GetRole( bot, event.command.guild_id, Roles::BullyTarget ) ).get_members();

			std::erase_if( roll_table, [ & ]( auto const& mem ) {
				return admins.contains( mem.user_id ) or ( bully_targets.contains( mem.user_id ) and event.command.usr.id != mem.user_id );
			} );

			auto new_admin = co_await roll::DoRoleRoll(
				event,
				Roles::BullyTarget,
				roll_table,
				std::format( "🎲 {} is re-rolling the bully target!", event.command.usr.get_mention() ),
				roll::MakeResponsePair( "<@{}> is free! <@{}> is the new bully target. GET THEM!", "<@{}> is the new bully target. GET THEM!" ) );
		}

		std::vector< dpp::component > GetInputHandlers()
		{
			return {};
		}
	};
} // namespace iter8::shop
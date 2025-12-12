#include "AdminRollCog.h"

#include "Model/InventoryItem.h"
#include "Model/Timestamps.h"
#include "Shop/Item.h"
#include "Utils/Rolls.h"

namespace iter8
{
	static bool IsCorrectTime()
	{
		using namespace std::chrono;

		auto tp = system_clock::now();
		auto dp = floor< std::chrono::days >( tp );

		auto day = weekday{ dp };
		auto tod = hh_mm_ss{ tp - dp };

		auto const threshold = duration_cast< seconds >( 13h );
		auto const since_midnight = duration_cast< seconds >( tod.to_duration() );

		return ( day == Friday ) and ( since_midnight >= threshold );
	}

	static bool IsFirstRoll( TimePoint last_roll )
	{
		using namespace std::chrono;

		auto tp = system_clock::now();
		return ( last_roll - tp ) > std::chrono::days{ 6 };
	}

	AdminRollCog::AdminRollCog( Context& ctx )
		: Cog( ctx )
	{
		AddCommand( { "roll_admin", "Commence the weekly admin dice roll." }, std::bind_front( &AdminRollCog::OnRollAdminCommand, this ) );
	}

	dpp::task< void > AdminRollCog::OnRollAdminCommand( dpp::slashcommand_t const& event )
	{
		if ( not IsCorrectTime() )
		{
			co_await event.co_reply( "Wait till you've had your samosa!" );
			co_return;
		}

		auto timestamps = ctx_.db.SelectOne< Timestamps >();
		if ( timestamps and not IsFirstRoll( timestamps->last_roll ) )
		{
			co_await event.co_reply( "The dice has already been rolled, respect its result." );
			co_return;
		}

		auto reply = dpp::message{ "Rolling admin..." }.set_flags( dpp::m_ephemeral );
		co_await event.co_reply( reply );

		auto update = timestamps.value_or( {} );
		update.last_roll = std::chrono::system_clock::now();
		ctx_.db.InsertOrUpdate( update );

		auto roll_table = co_await GetNonBotMembers( ctx_.bot, event.command.guild_id );
		auto extra_rolls = ctx_.db.Select< InventoryItem >( db::Where(
			db::WhereParam( &InventoryItem::item_id, db::ForeignKey< ShopItem >{ db::ToId( shop::ItemId::AdminTicket ) } ),
			db::WhereParam( &InventoryItem::used, false ) ) );

		for ( auto roll : extra_rolls )
		{
			roll_table.push_back( co_await GetMember( ctx_.bot, roll.user_id.value ) );
		}

		auto new_admin = co_await roll::DoRoleRoll(
			event,
			Roles::Admin,
			roll_table,
			"🎲 Let's roll the dice! 🎲",
			roll::MakeResponsePair( "<@{}> is dead. Long live <@{}>.", "Long live <@{}>." ) );

		co_await ctx_.bot.co_sleep( 2 );

		std::erase_if( roll_table, [ = ]( auto const& mem ) { return mem.user_id == new_admin; } );

		co_await roll::DoRoleRoll(
			event,
			Roles::BullyTarget,
			roll_table,
			"🎲 Who's getting bullied? 🎲",
			roll::MakeResponsePair( "<@{}> is free! <@{}> is the new bully target. GET THEM!", "<@{}> is the new bully target. GET THEM!" ) );
	}
} // namespace iter8
#pragma once

#include "Core/Discord.h"
#include "Shop/Item.h"

namespace iter8::shop
{
	auto constexpr SaleEventName = "Black Friday Sale!";

	class BlackFridaySale : public Handler
	{
	public:
		BlackFridaySale( Context& ctx )
			: Handler( ctx )
		{}

		dpp::task< void > HandlePurchase( dpp::interaction_create_t const& event, std::map< std::string, std::any > const& params ) override
		{
			if ( not event.owner )
				co_return;

			auto& bot = *event.owner;

			auto events = co_await GetEvents( bot, event.command.guild_id );

			auto it = std::ranges::find_if( events, [ & ]( auto const& kv ) { return kv.second.name == SaleEventName; } );

			using clock = std::chrono::system_clock;
			if ( it != events.end() )
			{
				auto& sale_event = it->second;
				auto end = clock::from_time_t( sale_event.scheduled_end_time );
				auto new_end = end + std::chrono::minutes( 30 );
				sale_event.scheduled_end_time = clock::to_time_t( new_end );

				co_await bot.co_guild_event_edit( sale_event );
				co_await event.co_follow_up( std::format( "The Black Friday Sale was extended by {} by another 30 minutes!", event.command.usr.get_mention() ) );
			}
			else
			{
				auto now = clock::now();
				auto start = clock::to_time_t( now );
				auto end = clock::to_time_t( now + std::chrono::minutes( 30 ) );

				auto new_event = dpp::scheduled_event{};
				new_event.guild_id = event.command.guild_id;
				new_event.name = SaleEventName;
				new_event.scheduled_start_time = start;
				new_event.creator_id = event.command.usr.id;
				new_event.description = "Get half off all shop items!";
				new_event.entity_type = dpp::eet_external;
				new_event.privacy_level = dpp::ep_guild_only;
				co_await bot.co_guild_event_create( new_event );

				co_await event.co_follow_up( std::format( "{} started a sale! Get 50% off for the next 30 minutes!", event.command.usr.get_mention() ) );
			}
		}

		std::vector< InputType > GetInputHandlers()
		{
			return {};
		}
	};
} // namespace iter8::shop
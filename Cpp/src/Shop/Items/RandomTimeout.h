#pragma once

#include "Core/Discord.h"
#include "Core/Random.h"
#include "Shop/Item.h"

namespace iter8::shop
{
	class RandomTimeout : public Handler
	{
	public:
		RandomTimeout( Context& ctx )
			: Handler( ctx )
		{}

		dpp::task< void > HandlePurchase( dpp::interaction_create_t const& event, std::map< std::string, std::any > const& params ) override
		{
			auto& bot = *event.owner;

			int duration = std::any_cast< int >( params.at( "duration" ) );

			auto guild = co_await GetGuild( bot, Guilds::Default );
			auto& member = Random( guild.members | std::views::values );

			auto now = std::chrono::system_clock::now();

			auto start = std::max( now, std::chrono::system_clock::from_time_t( member.communication_disabled_until ) );
			auto until = start + std::chrono::minutes( duration );

			std::optional< std::string > text = params.contains( "text" ) ? std::any_cast< std::string >( params.at( "text" ) ) : std::optional< std::string >{};
			auto extra_reason = text.transform( []( auto const& str ) { return std::format( " because {}", str ); } ).value_or( "" );
			auto reason = std::format( "{} decided to bully someone at random{}.", event.command.usr.get_mention(), extra_reason );

			co_await bot.set_audit_reason( reason )
				.co_guild_member_timeout( member.guild_id, member.user_id, std::chrono::system_clock::to_time_t( until ) );
		}

		std::vector< InputType > GetInputHandlers()
		{
			return { InputType::Duration };
		}
	};
} // namespace iter8::shop
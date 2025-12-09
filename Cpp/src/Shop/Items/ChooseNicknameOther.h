#pragma once

#include "Core/Discord.h"
#include "Shop/Item.h"

namespace iter8::shop
{
	class ChooseNicknameOther : public Handler
	{
	public:
		ChooseNicknameOther( db::Connection& db )
			: Handler( db )
		{}

		dpp::task< void > HandlePurchase( dpp::interaction_create_t& event, std::map< std::string, std::any > const& params ) override
		{
			if ( not event.owner )
				co_return;

			auto& bot = *event.owner;

			auto user = std::any_cast< dpp::snowflake >( params.at( "user" ) );
			auto nickname = std::any_cast< std::string >( params.at( "text" ) );

			auto member = co_await GetMember( bot, user );
			member.set_nickname( nickname );

			co_await bot.co_guild_edit_member( member );
		}

		std::vector< dpp::component > GetInputHandlers()
		{
			return {};
		}
	};
} // namespace iter8::shop
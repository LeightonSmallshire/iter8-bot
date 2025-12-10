#pragma once

#include "Core/Discord.h"
#include "Shop/Item.h"

namespace iter8::shop
{
	class ChooseNicknameSelf : public Handler
	{
	public:
		ChooseNicknameSelf( Context& ctx )
			: Handler( ctx )
		{}

		dpp::task< void > HandlePurchase( dpp::interaction_create_t const& event, std::map< std::string, std::any > const& params ) override
		{
			if ( not event.owner )
				co_return;

			auto& bot = *event.owner;

			auto nickname = std::any_cast< std::string >( params.at( "text" ) );

			auto member = co_await GetMember( bot, event.command.usr.id );
			member.set_nickname( nickname );

			co_await bot.co_guild_edit_member( member );
		}

		std::vector< InputType > GetInputHandlers()
		{
			return { InputType::Text };
		}
	};
} // namespace iter8::shop
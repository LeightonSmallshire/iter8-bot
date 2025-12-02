#include "BotBrokenCog.h"

#include "Core/Common.h"

#include <print>
#include <ranges>

namespace iter8
{
	BotBrokenCog::BotBrokenCog( Context& ctx )
		: Cog( ctx )
	{
		auto user_param = CommandArgumentDefinition{
			.type = dpp::co_user,
			.name = "user",
			.required = false
		};

		AddCommand( { "broken", "Bot is broken", { user_param } }, std::bind_front( &BotBrokenCog::OnBrokenCommand, this ) );
		AddCommand( { "working", "Bot is working", { user_param } }, std::bind_front( &BotBrokenCog::OnWorkingCommand, this ) );
		AddListener( ctx_.bot.on_message_create, std::bind_front( &BotBrokenCog::OnMessage, this ) );
	}

	dpp::task< void > BotBrokenCog::OnBrokenCommand( dpp::slashcommand_t const& event )
	{
		auto thinking = event.co_thinking( true );

		auto target = GetParameter< dpp::snowflake >( event, "user" ).value_or( Users::Leighton );
		std::println( "Broken command from {}", event.command.get_issuing_user().username );

		auto const& channels = event.command.get_guild().channels;
		auto it = std::ranges::find( channels, Channels::ParadiseBotBrokenSpam );
		auto channel = it != channels.end() ? Channels::ParadiseBotBrokenSpam : event.command.get_channel().id;

		auto message = dpp::message( channel, std::format( "<@{}> bot broken", target.str() ) );

		co_await ctx_.bot.co_message_create( message );
		co_await thinking;
		co_await event.co_delete_original_response();
	}

	dpp::task< void > BotBrokenCog::OnWorkingCommand( dpp::slashcommand_t const& event )
	{
		auto thinking = event.co_thinking( true );

		auto target = GetParameter< dpp::snowflake >( event, "user" ).value_or( Users::Leighton );
		std::println( "Working command from {}", event.command.get_issuing_user().username );

		auto const& channels = event.command.get_guild().channels;
		auto it = std::ranges::find( channels, Channels::ParadiseBotBrokenSpam );
		auto channel = it != channels.end() ? Channels::ParadiseBotBrokenSpam : event.command.get_channel().id;

		auto message = dpp::message( channel, std::format( "<@{}> bot working", target.str() ) );

		co_await thinking;
		co_await event.co_delete_original_response();
		co_await ctx_.bot.co_message_create( message );
	}

	dpp::task< void > BotBrokenCog::OnMessage( dpp::message_create_t const& event )
	{
		if ( event.msg.author.id == ctx_.bot.me.id )
			co_return;

		auto msg = ToLower( event.msg.content );

		if ( msg.contains( "bot broken" ) )
			co_await event.co_reply( "No U" );
		if ( msg.contains( "boot broekn" ) )
			co_await event.co_reply( "No broekn" );
	}
} // namespace iter8
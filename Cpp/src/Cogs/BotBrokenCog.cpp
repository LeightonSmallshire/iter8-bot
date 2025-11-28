#include "BotBrokenCog.h"

#include "Core/Common.h"

#include <print>
#include <ranges>

namespace iter8
{
	BotBrokenCog::BotBrokenCog( dpp::cluster& bot )
		: Cog( bot )
	{
		auto user_param = CommandArgumentDefinition{
			.type = dpp::co_user,
			.name = "user",
			.required = false
		};

		AddCommand( { "broken", "Bot is broken", { user_param } }, std::bind_front( &BotBrokenCog::OnBrokenCommand, this ) );
		AddCommand( { "working", "Bot is working", { user_param } }, std::bind_front( &BotBrokenCog::OnWorkingCommand, this ) );
		AddListener( bot_.on_message_create, std::bind_front( &BotBrokenCog::OnMessage, this ) );
	}

	dpp::task< void > BotBrokenCog::OnBrokenCommand( dpp::slashcommand_t const& event )
	{
		co_await event.co_thinking( true );

		auto target = GetParameter< dpp::snowflake >( event, "user" ).value_or( Users::Leighton );
		std::println( "Broken command from {}", event.command.get_issuing_user().username );

		auto const& channels = event.command.get_guild().channels;
		auto it = std::ranges::find( channels, Channels::ParadiseBotBrokenSpam );
		auto channel = it != channels.end() ? Channels::ParadiseBotBrokenSpam : event.command.get_channel().id;

		auto message = dpp::message( channel, std::format( "<@{}> bot broken", target.str() ) );
		co_await bot_.co_message_create( message );

		co_await event.co_delete_original_response();
	}

	dpp::task< void > BotBrokenCog::OnWorkingCommand( dpp::slashcommand_t const& event )
	{
		co_await event.co_thinking( true );

		auto target = GetParameter< dpp::snowflake >( event, "user" ).value_or( Users::Leighton );
		std::println( "Working command from {}", event.command.get_issuing_user().username );

		auto const& channels = event.command.get_guild().channels;
		auto it = std::ranges::find( channels, Channels::ParadiseBotBrokenSpam );
		auto channel = it != channels.end() ? Channels::ParadiseBotBrokenSpam : event.command.get_channel().id;

		auto message = dpp::message( channel, std::format( "<@{}> bot working", target.str() ) );
		co_await bot_.co_message_create( message );

		co_await event.co_delete_original_response();
	}

	dpp::task< void > BotBrokenCog::OnMessage( dpp::message_create_t const& event )
	{
		if ( event.msg.author.id == bot_.me.id )
			co_return;

		auto to_lower = []( std::string_view str ) {
			auto to_lower = []( char c ) { return std::tolower( c ); };
			return str | std::views::transform( to_lower ) | std::ranges::to< std::string >();
		};

		if ( to_lower( event.msg.content ).contains( "bot broken" ) )
			co_await event.co_reply( "No U" );
		if ( to_lower( event.msg.content ).contains( "boot broekn" ) )
			co_await event.co_reply( "No broekn" );
	}
} // namespace iter8
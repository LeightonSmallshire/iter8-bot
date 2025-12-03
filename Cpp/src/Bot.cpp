#include "Bot.h"

#include "Cogs/BotBrokenCog.h"
#include "Cogs/DevCog.h"

#include "Model/User.h"
#include "Model/Log.h"

#include "Logging/Log.h"

#include <generator>

namespace iter8
{
	DiscordBot::DiscordBot()
		: ctx_{
			.bot{ std::getenv( "DISCORD_TOKEN" ), dpp::i_default_intents | dpp::i_guild_members | dpp::i_message_content | dpp::i_guild_message_reactions },
			.db{ "data/storage.db" }
		}
	{
		Init();

		log::Info( "Bot starting..." );
		ctx_.bot.start( dpp::st_wait );
	}

	void DiscordBot::Init()
	{
		InitDB();
		InitLog();
		InitBot();
	}

	void DiscordBot::InitDB()
	{
		ctx_.db.Init< User >( /*truncate=*/true );
		ctx_.db.Init< Log >( /*truncate=*/true );
	}

	void DiscordBot::InitLog()
	{
		log::Init( ctx_.db );
	}

	void DiscordBot::InitBot()
	{
		RegisterCog< BotBrokenCog >();
		RegisterCog< DevCog >();

		ctx_.bot.on_ready( std::bind_front( &DiscordBot::OnReady, this ) );
		ctx_.bot.on_autocomplete( std::bind_front( &DiscordBot::OnAutocomplete, this ) );
		ctx_.bot.on_log( std::bind_front( &DiscordBot::OnLog, this ) );
	}

	dpp::task< void > DiscordBot::OnReady( dpp::ready_t const& e )
	{
		log::Info( "Discord bot logged in as {} (ID: {})", ctx_.bot.me.username, ctx_.bot.me.id );

		co_await CalculateUserCredit();

		auto dms = Users::Trusted | std::views::transform( [ this ]( auto id ) { return ctx_.bot.co_direct_message_create( id, dpp::message( "Bot connected" ) ); } );
		co_await AwaitAll( dms );
	}

	dpp::task< void > DiscordBot::OnAutocomplete( dpp::autocomplete_t const& e )
	{
		if ( not ctx_.autocomplete_handlers.contains( e.name ) )
			co_return;

		auto const& handlers = ctx_.autocomplete_handlers[ e.name ];
		auto it = std::ranges::find_if( e.options, [ & ]( auto const& o ) {
			return o.focused and handlers.contains( o.name );
		} );

		if ( it == e.options.end() )
			co_return;

		co_await handlers.at( it->name )( e, *it );
	}

	void DiscordBot::OnLog( dpp::log_t const& e )
	{
		switch ( e.severity )
		{
			case dpp::ll_trace:
				log::Trace( "{}", e.message );
				break;
			case dpp::ll_debug:
				log::Debug( "{}", e.message );
				break;
			case dpp::ll_info:
				log::Info( "{}", e.message );
				break;
			case dpp::ll_warning:
				log::Warn( "{}", e.message );
				break;
			case dpp::ll_error:
				log::Error( "{}", e.message );
				break;
			case dpp::ll_critical:
			default:
				log::Critical( "{}", e.message );
				break;
		}
	}

	static double ParseAuditTimestamp( std::string_view s )
	{
		if ( s.size() >= 2 && s.front() == '"' && s.back() == '"' )
		{
			s.remove_prefix( 1 );
			s.remove_suffix( 1 );
		}

		if ( s.empty() || s == "null" )
			throw std::runtime_error( "Missing audit timestamp." );

		// Parse "2025-11-19T10:49:10.093000+00:00"
		std::chrono::sys_time< std::chrono::microseconds > tp{};
		std::istringstream iss( std::string{ s } );
		iss >> std::chrono::parse( "%FT%T%Ez", tp );

		if ( iss.fail() )
			throw std::runtime_error( "Failed to parse audit timestamp." );

		auto since_epoch = tp.time_since_epoch();
		auto secs = std::chrono::duration_cast< std::chrono::duration< double > >( since_epoch );
		return secs.count();
	}

	dpp::task< void > DiscordBot::CalculateUserCredit()
	{
		auto constexpr AuditLogUpdateType = "communication_disabled_until";
		auto const page_size = 100;

		auto leaderboard = Users::All | std::views::transform( []( auto id ) { return std::make_pair( id, User{ db::ToId( id ), 0, 0, 0 } ); } ) | std::ranges::to< std::map >();
		dpp::snowflake before{};

		while ( true )
		{
			auto audit_result = ctx_.bot.co_guild_auditlog_get( Guilds::Default, 0, dpp::audit_type::aut_member_update, before, 0, 100 );
			auto log = co_await Result< dpp::auditlog >( audit_result );

			if ( log.entries.empty() )
				break;

			for ( auto const& entry : log.entries )
			{
				auto get_moderator = ctx_.bot.co_guild_get_member( Guilds::Default, entry.user_id );
				auto get_member = ctx_.bot.co_guild_get_member( Guilds::Default, entry.target_id );
				auto get_user = ctx_.bot.co_user_get( entry.target_id );

				auto moderator = co_await Result< dpp::guild_member >( get_moderator );
				auto member = co_await Result< dpp::guild_member >( get_member );
				auto user = co_await Result< dpp::user_identified >( get_user );

				if ( member.is_guild_owner() or user.is_bot() )
					continue;

				if ( std::ranges::none_of( entry.changes, [ & ]( auto const& key ) { return key == AuditLogUpdateType; }, &dpp::audit_change::key ) )
					continue;

				for ( auto const& change : entry.changes )
				{
					auto created_at = entry.id.get_creation_time();

					bool timeout_added = change.old_value.empty() and not change.new_value.empty();
					bool timeout_changed = not change.old_value.empty() and not change.new_value.empty();
					bool timeout_removed = not change.old_value.empty() and change.new_value.empty();

					if ( ( timeout_added or timeout_changed ) and moderator.is_guild_owner() )
						break;

					auto& record = leaderboard[ entry.target_id ];
					if ( timeout_added )
					{
						auto end = ParseAuditTimestamp( change.new_value );
						record.count += 1;
						record.duration += end - created_at;
						record.credit += end - created_at;
					}

					if ( timeout_changed )
					{
						auto end = ParseAuditTimestamp( change.new_value );
						auto prev_end = ParseAuditTimestamp( change.old_value );
						record.duration += end - prev_end;
						record.credit += end - prev_end;
					}

					if ( timeout_removed )
					{
						auto prev_end = ParseAuditTimestamp( change.old_value );
						record.duration = created_at - prev_end;
						record.credit = created_at - prev_end;
					}
				}
			}

			if ( log.entries.size() < 100 )
				break;

			before = log.entries.back().id;
		}



		ctx_.db.Insert( leaderboard | std::views::values );
	}

} // namespace iter8
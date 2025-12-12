#include "TimeoutCog.h"

#include "Model/User.h"
#include "Logging/Log.h"

namespace iter8
{
	TimeoutCog::TimeoutCog( Context& ctx )
		: Cog( ctx )
	{
		AddCommand( { "leaderboard", "Show timeout leaderboard" }, std::bind_front( &TimeoutCog::OnLeaderboardCommand, this ) );

		AddListener( ctx_.bot.on_guild_member_update, std::bind_front( &TimeoutCog::OnMemberUpdate, this ) );
	}

	dpp::task< void > TimeoutCog::OnLeaderboardCommand( dpp::slashcommand_t const& event )
	{
		co_await event.co_thinking();

		auto leaderboard = ctx_.db.Select< User >( {}, db::OrderBy( db::OrderParam( &User::count, db::Ordering::Desc ), db::OrderParam( &User::duration, db::Ordering::Desc ) ) );

		auto embed = dpp::embed{};
		embed.set_title( "👑 Timeout Leaderboard 👑" );
		embed.set_color( dpp::colors::cinnabar );

		for ( auto&& [ rank, user ] : std::views::enumerate( leaderboard ) )
		{
			auto tp = TimePoint( std::chrono::duration_cast< std::chrono::system_clock::duration >( std::chrono::duration< double >( user.duration ) ) );
			auto value = std::format( "**{}** Timeout{} {:%T}", user.count, user.count != 1 ? "s" : "", std::chrono::round< std::chrono::seconds >( tp ) );
			auto member = co_await GetMember( ctx_.bot, user.id );

			std::string field_name{};
			auto nickname = member.get_nickname();
			auto name = nickname.empty() ? ( co_await GetUser( ctx_.bot, user.id ) ).global_name : nickname;
			switch ( rank )
			{
				case 0:
					field_name = std::format( "🥇 {}", name );
					break;
				case 1:
					field_name = std::format( "🥈 {}", name );
					break;
				case 2:
					field_name = std::format( "🥉 {}", name );
					break;
				default:
					field_name = std::format( "{}: {}", rank + 1, name );
					break;
			}

			embed.add_field( field_name, value );
		}

		dpp::message msg( embed );
		co_await event.co_follow_up( msg );
	}

	dpp::task< std::optional< TimeoutInfo > > FindTimeoutInfo( dpp::cluster& bot, dpp::snowflake target )
	{
		dpp::snowflake before{};

		auto filter_predicate = [ & ]( auto const& log ) {
			return log.target_id == target and
				   std::ranges::contains( log.changes, "communication_disabled_until", &dpp::audit_change::key );
		};

		while ( true )
		{
			auto audit_result = bot.co_guild_auditlog_get( Guilds::Default, 0, dpp::audit_type::aut_member_update, before, 0, 5 );
			auto log = co_await Result< dpp::auditlog >( audit_result );

			auto filtered_logs = log.entries | std::views::filter( filter_predicate ) | std::ranges::to< std::vector >();

			for ( dpp::audit_entry const& entry : log.entries )
			{
				co_return TimeoutInfo{ entry.user_id, entry.reason.empty() ? "Fun!" : entry.reason };
			}

			if ( filtered_logs.size() < 5 )
				break;

			before = filtered_logs.back().id;
		}

		co_return {};
	}

	dpp::task< void > TimeoutCog::OnMemberUpdate( dpp::guild_member_update_t const& event )
	{
		auto from_time_t = []( auto t ) -> std::optional< TimePoint > {
			if ( t == 0 )
				return {};

			return std::chrono::system_clock::from_time_t( t );
		};

		auto now = std::chrono::system_clock::now();

		auto before = ctx_.timeouts[ event.updated.user_id ];
		auto after = from_time_t( event.updated.communication_disabled_until );

		if ( before == after )
			co_return;

		ctx_.timeouts[ event.updated.user_id ] = after;

		bool timeout_applied = after and not before;
		bool timeout_removed = before and not after;
		bool timeout_extended = before and after and ( before < after );

		bool has_changed = timeout_applied or timeout_extended or timeout_removed;

		if ( not has_changed )
			co_return;

		double duration_to_add;
		if ( timeout_applied )
			duration_to_add = DurationToDouble( *after - now );
		else if ( timeout_removed )
			duration_to_add = DurationToDouble( now - *before );
		else if ( timeout_extended )
			duration_to_add = DurationToDouble( *after - *before );

		log::Info( "Timeout in {} : {} : until {}", event.updating_guild.name, event.updated.get_nickname(), after.value_or( {} ) );

		auto update_info = co_await FindTimeoutInfo( ctx_.bot, event.updated.user_id );

		bool do_update = update_info and ( update_info->moderator != event.updating_guild.owner_id or timeout_removed );
		if ( not do_update )
			co_return;

		auto record = ctx_.db.SelectOne< User >( db::Where( db::WhereParam( &User::id, db::ToId( event.updated.user_id ) ) ) );
		User user = record.value_or( User{ db::ToId( event.updated.user_id ) } );

		user.count++;
		user.duration += duration_to_add;
		user.credit += duration_to_add;

		if ( record )
			ctx_.db.Update( user );
		else
			ctx_.db.Insert( user );

		if ( timeout_applied or timeout_extended )
			co_await OnMemberTimeout( event.updating_guild, event.updated, *after, update_info );
		else
			co_await OnMemberUntimeout( event.updating_guild, event.updated, update_info );
	}

	dpp::task< void > TimeoutCog::OnMemberTimeout( dpp::guild const& guild, dpp::guild_member const& member, TimePoint ts, std::optional< TimeoutInfo > timeout_info )
	{
		auto const& channels = guild.channels;
		auto it = std::ranges::find( channels, Channels::Clockwork );

		if ( it == channels.end() )
		{
			log::Critical( "Couldn't find channel 'clockwork-bot' to post in" );
			co_return;
		}

		auto time = std::chrono::system_clock::to_time_t( ts );
		if ( not timeout_info )
		{
			auto message = dpp::message( *it, std::format( "{} was timed out {}", member.get_mention(), dpp::utility::timestamp( time, dpp::utility::tf_relative_time ) ) );
			message.flags |= dpp::m_suppress_notifications;
			co_await ctx_.bot.co_message_create( message );
		}
		else
		{
			auto msg_str = std::format( "{} was timed out by <@{}> for **{}** {}", member.get_mention(), timeout_info->moderator.str(), timeout_info->reason, dpp::utility::timestamp( time, dpp::utility::tf_relative_time ) );
			auto message = dpp::message( *it, std::move( msg_str ) );
			message.flags |= dpp::m_suppress_notifications;
			co_await ctx_.bot.co_message_create( message );
		}
	}

	dpp::task< void > TimeoutCog::OnMemberUntimeout( dpp::guild const& guild, dpp::guild_member const& member, std::optional< TimeoutInfo > timeout_info )
	{
		auto const& channels = guild.channels;
		auto it = std::ranges::find( channels, Channels::Clockwork );

		if ( it == channels.end() )
		{
			log::Critical( "Couldn't find channel 'clockwork-bot' to post in" );
			co_return;
		}

		if ( not timeout_info )
		{
			auto message = dpp::message( *it, std::format( "{} was freed from their time out.", member.get_mention() ) );
			message.flags |= dpp::m_suppress_notifications;
			co_await ctx_.bot.co_message_create( message );
		}
		else
		{
			auto msg_str = std::format( "{} was freed from their time out by <@{}>", member.get_mention(), timeout_info->moderator.str() );
			auto message = dpp::message( *it, std::move( msg_str ) );
			message.flags |= dpp::m_suppress_notifications;
			co_await ctx_.bot.co_message_create( message );
		}
	}
} // namespace iter8
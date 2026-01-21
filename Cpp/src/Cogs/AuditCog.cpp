#include "AuditCog.h"
#include "Model/AuditLog.h"
#include "Logging/Log.h"


namespace iter8
{
	AuditCog::AuditCog( Context& ctx )
		: Cog( ctx )
	{
		// AddCommand( { "leaderboard", "Show timeout leaderboard" }, std::bind_front( &AuditCog::OnLeaderboardCommand, this ) );
		AddListener( ctx_.bot.on_ready, std::bind_front( &AuditCog::doRefresh, this ) );
		// doRefresh().sync_wait();
	}

	dpp::task< void > AuditCog::doRefresh( dpp::ready_t const& event )
	{
		// block simultaneous calls
		// std::scoped_lock lock( updating_mutex_ );

		dpp::auditlog log;
		do
		{
			auto const latest_db_event = ctx_.db.SelectOne< AuditLogEntry >( {}, db::OrderBy( db::Param( &AuditLogEntry::id, db::Ordering::Desc ) ) );

            // todo: check behaviour of DPP
            // after=0              oldest first
            // before=0             youngest first
            // after=0&before=0     youngest first

            // Impl:
            // std::string parameters = utility::make_url_parameters({
			// 	{"user_id", user_id},
			// 	{"action_type", action_type},
			// 	{"before", before},
			// 	{"after", after},
			// 	{"limit", limit},
			// });
			// rest_request<auditlog>(this, API_PATH "/guilds", std::to_string(guild_id), "audit-logs" + parameters, m_get, "", callback);

			auto const after = static_cast< uint64_t >( latest_db_event.value_or( {} ).id );
			auto audit_result = ctx_.bot.co_guild_auditlog_get( Guilds::Default, 0, 0, 0, after, 100 );
			log = co_await Result< dpp::auditlog >( audit_result );

			std::cout << "Pulled " << log.entries.size() << " events" << std::endl;

			for ( dpp::audit_entry const& entry : log.entries )
			{
				ctx_.db.Insert( AuditLogEntry{
					db::ToId( entry.id ),
					static_cast< uint64_t >( entry.target_id ),
					static_cast< uint64_t >( entry.user_id ),
					entry.type,
					entry.reason.empty() ? std::nullopt : std::optional{ entry.reason },
					{} // todo; store entry.extra as a blob / whatever
				} );

				for ( dpp::audit_change const& change : entry.changes )
				{
					ctx_.db.Insert( AuditLogChange{
						db::ToId( entry.id ),
						change.key,
						change.old_value,
						change.new_value } );
				}
			}
		} while ( log.entries.size() > 0 );
	}

	/*
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

	dpp::task< void > AuditCog::OnMemberUpdate( dpp::guild_member_update_t const& event )
	{
		auto from_time_t = []( auto t ) -> std::optional< TimePoint > {
			if ( t == 0 )
				return {};

			return std::chrono::system_clock::from_time_t( t );
		};

		auto now = std::chrono::system_clock::now();

		auto before = ctx_.timeouts[ event.updated.user_id ];
		auto after = from_time_t( event.updated.communication_disabled_until );

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
		user.duration += duration_to_add;

		if ( record )
			ctx_.db.Update( user, db::Where( db::WhereParam( &User::id, user.id ) ) );
		else
			ctx_.db.Insert( user );

		if ( timeout_applied or timeout_extended )
			co_await OnMemberTimeout( event.updating_guild, event.updated, *after, update_info );
		else
			co_await OnMemberUntimeout( event.updating_guild, event.updated, update_info );
	}

	dpp::task< void > AuditCog::OnMemberTimeout( dpp::guild const& guild, dpp::guild_member const& member, TimePoint ts, std::optional< TimeoutInfo > timeout_info )
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

	dpp::task< void > AuditCog::OnMemberUntimeout( dpp::guild const& guild, dpp::guild_member const& member, std::optional< TimeoutInfo > timeout_info )
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
	}*/
} // namespace iter8

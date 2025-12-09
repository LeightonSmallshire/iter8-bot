#pragma once

#include "Common.h"
#include "Database/Model.h"

#include "dpp/dpp.h"

#include <optional>

namespace iter8
{
	template < typename T >
	concept SlashCommandHandler = Callable< T, dpp::task< void >, dpp::slashcommand_t const& >;

	using AutocompleteHandler = std::function< dpp::task< void >( dpp::autocomplete_t const&, dpp::command_option const& ) >;
	using ComponentHandler = std::function< dpp::task< void >( dpp::interaction_create_t const& ) >;

	template < typename T, typename event_t >
	concept ListenerHandler = Callable< T, dpp::task< void >, event_t const& >;

	struct CommandArgumentDefinition
	{
		dpp::command_option_type type;
		std::string name;
		std::string description{};
		bool required{};
		AutocompleteHandler autocomplete{};
	};

	struct CommandDefinition
	{
		std::string name;
		std::string description{};
		std::vector< CommandArgumentDefinition > parameters;
	};


	struct Guilds
	{
		static constexpr dpp::snowflake TestServer = 1427287847085281382;
		static constexpr dpp::snowflake Paradise = 1416007094339113071;
		static constexpr dpp::snowflake Innov8 = 1325821294427766784;
		static constexpr dpp::snowflake Innov8_DevOps = 1425873966035238975;
		static inline dpp::snowflake Default = IS_LIVE ? Paradise : TestServer;
	};

	struct Channels
	{
	private:
		static constexpr dpp::snowflake ParadiseBotBrokenSpam = 1427971106920202240;
		static constexpr dpp::snowflake ParadiseClockwork = 1416059475873239181;
		static constexpr dpp::snowflake ParadiseStockMarketSpam = 1440735848801894640;
		static constexpr dpp::snowflake ParadiseStockMarketSummary = 1440735818644852829;
		static constexpr dpp::snowflake TestServerBotSpam = 1432698704191815680;
		static constexpr dpp::snowflake TestServerStockSpam = 1440731650307915816;
		static constexpr dpp::snowflake TestServerStockSummary = 1440731630070403284;

	public:
		static inline dpp::snowflake BotBrokenSpam = IS_LIVE ? ParadiseBotBrokenSpam : TestServerBotSpam;
		static inline dpp::snowflake Clockwork = IS_LIVE ? ParadiseClockwork : TestServerBotSpam;
		static inline dpp::snowflake StockMarketSpam = IS_LIVE ? ParadiseStockMarketSpam : TestServerStockSpam;
		static inline dpp::snowflake StockMarketSummary = IS_LIVE ? ParadiseStockMarketSummary : TestServerStockSummary;
	};

	struct Roles
	{
	private:
		static constexpr dpp::snowflake ParadiseAdmin = 1416037888847511646;
		static constexpr dpp::snowflake ParadiseBullyTarget = 1432752493670170624;

		static constexpr dpp::snowflake TestServerAdmin = 1433782662765477909;
		static constexpr dpp::snowflake TestServerBullyTarget = 1433810360166777002;

	public:
		static inline dpp::snowflake Admin = IS_LIVE ? ParadiseAdmin : TestServerAdmin;
		static inline dpp::snowflake BullyTarget = IS_LIVE ? ParadiseBullyTarget : TestServerBullyTarget;
	};

	struct Users
	{
		static constexpr dpp::snowflake Nathan = 1326156803108503566;
		static constexpr dpp::snowflake Leighton = 1416017385596653649;
		static constexpr dpp::snowflake Charlotte = 1401855871633330349;
		static constexpr dpp::snowflake Ed = 1356197937520181339;
		static constexpr dpp::snowflake Matt = 1333425159729840188;
		static constexpr dpp::snowflake Tom = 1339198017324187681;
		static constexpr dpp::snowflake Gary = 1359152866727821342;

		static constexpr std::array Trusted = { Nathan };
		static constexpr std::array All = { Nathan, Leighton, Charlotte, Ed, Matt, Tom, Gary };

		static bool IsTrusted( dpp::snowflake id )
		{
			return std::ranges::contains( Trusted, id );
		}
	};


	namespace detail
	{
		inline dpp::guild_member* FindGuildMember( dpp::snowflake const guild_id, dpp::snowflake const user_id )
		{
			using namespace dpp;
			guild* g = find_guild( guild_id );
			if ( g )
			{
				auto gm = g->members.find( user_id );
				if ( gm != g->members.end() )
				{
					return &gm->second;
				}
			}

			return nullptr;
		}
	} // namespace detail

	template < typename T >
	std::optional< T > GetParameter( dpp::slashcommand_t const& e, std::string const& param )
	{
		auto opt = e.get_parameter( param );
		if ( std::holds_alternative< std::monostate >( opt ) )
			return std::nullopt;

		if ( auto value = std::get_if< T >( &opt ) )
			return *value;

		return std::nullopt;
	}

	inline dpp::task< dpp::guild > GetGuild( dpp::cluster& bot, dpp::snowflake id )
	{
		if ( auto guild = dpp::find_guild( id ) )
			co_return *guild;

		auto result = co_await bot.co_guild_get( id );
		co_return std::get< dpp::guild >( result.value );
	}

	inline dpp::task< dpp::role > GetRole( dpp::cluster& bot, dpp::snowflake guild_id, dpp::snowflake role_id )
	{
		if ( auto role = dpp::find_role( role_id ) )
			co_return *role;

		auto result = co_await bot.co_roles_get( guild_id );
		auto roles = std::get< dpp::role_map >( result.value );
		co_return roles.at( role_id );
	}

	inline dpp::task< dpp::guild_member > GetMember( dpp::cluster& bot, dpp::snowflake id )
	{
		if ( auto member = detail::FindGuildMember( Guilds::Default, id ) )
			co_return *member;

		auto result = co_await bot.co_guild_get_member( Guilds::Default, id );
		co_return std::get< dpp::guild_member >( result.value );
	}
	inline dpp::task< dpp::guild_member > GetMember( dpp::cluster& bot, db::ID id )
	{
		co_return co_await GetMember( bot, std::to_underlying( id ) );
	}

	inline dpp::task< dpp::user_identified > GetUser( dpp::cluster& bot, dpp::snowflake id )
	{
		if ( auto user = dpp::find_user( id ) )
			co_return *user;

		auto result = co_await bot.co_user_get( id );
		co_return std::get< dpp::user_identified >( result.value );
	}
	inline dpp::task< dpp::user_identified > GetUser( dpp::cluster& bot, db::ID id )
	{
		co_return co_await GetUser( bot, std::to_underlying( id ) );
	}

	inline dpp::task< std::vector< dpp::guild_member > > GetNonBotMembers( dpp::cluster& bot, dpp::snowflake guild_id )
	{
		auto guild = co_await GetGuild( bot, guild_id );

		auto member_filter = []( dpp::guild_member const& member ) {
			auto user = member.get_user();
			return not member.is_guild_owner() and user and not user->is_bot();
		};
		co_return guild.members | std::views::values | std::views::filter( member_filter ) | std::ranges::to< std::vector >();
	}

	inline dpp::task< dpp::scheduled_event_map > GetEvents(dpp::cluster& bot, dpp::snowflake guild_id)
	{
		auto result = co_await bot.co_guild_events_get( guild_id );
		co_return std::get< dpp::scheduled_event_map >( result.value );
	}
} // namespace iter8
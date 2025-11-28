#pragma once

#include "dpp/dpp.h"

#include <filesystem>

namespace iter8
{
	static bool IS_LIVE = std::filesystem::exists( "/.dockerenv" );
	static bool IS_TESTING = not IS_LIVE;

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
		static constexpr dpp::snowflake TestServerBotSpam = 1432698704191815680;
		static constexpr dpp::snowflake ParadiseBotBrokenSpam = 1427971106920202240;
		static constexpr dpp::snowflake ParadiseClockwork = 1416059475873239181;
		static constexpr dpp::snowflake TestServerStockSpam = 1440731650307915816;
		static constexpr dpp::snowflake TestServerStockSummary = 1440731630070403284;
		static constexpr dpp::snowflake StockMarketSpam = 1440735848801894640;
		static constexpr dpp::snowflake StockMarketSummary = 1440735818644852829;
	};

	struct Roles
	{
		static constexpr dpp::snowflake Admin = 1416037888847511646;
		static constexpr dpp::snowflake DiceRoller = 1430187659678187581;
		static constexpr dpp::snowflake BullyTarget = 1432752493670170624;
	};

	struct Users
	{
		static constexpr dpp::snowflake Nathan = 1326156803108503566;
		static constexpr dpp::snowflake Leighton = 1416017385596653649;
		static constexpr dpp::snowflake Charlotte = 1401855871633330349;
		static constexpr dpp::snowflake Ed = 1356197937520181339;
		static constexpr dpp::snowflake Matt = 1333425159729840188;
		static constexpr dpp::snowflake Tom = 1339198017324187681;
	};



	
	template < typename F, typename R, typename... Args >
	concept Callable = requires( F&& f, Args&&... args ) {
		{ std::invoke( std::forward< F >( f ), std::forward< Args >( args )... ) } -> std::same_as< R >;
	};

} // namespace iter8
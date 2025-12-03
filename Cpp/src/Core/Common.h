#pragma once

#include "dpp/dpp.h"

#include <magic_enum/magic_enum.hpp>

#include <filesystem>
#include <source_location>

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

		static constexpr std::array Trusted = { Nathan, Leighton };

		static bool IsTrusted( dpp::snowflake id )
		{
			return std::ranges::contains( Trusted, id );
		}
	};

	template < typename F, typename R, typename... Args >
	concept Callable = requires( F&& f, Args&&... args ) {
		{ std::invoke( std::forward< F >( f ), std::forward< Args >( args )... ) } -> std::same_as< R >;
	};


	namespace detail
	{
		static consteval std::string_view Extract( std::string_view sv, std::string_view prefix, std::string_view suffix )
		{
			auto start = sv.find( prefix );

			if ( start == std::string_view::npos )
				start = 0;
			else
				start += prefix.size();

			auto end = sv.rfind( suffix );
			if ( suffix.empty() || end == std::string_view::npos || end <= start )
				end = sv.size();

			return sv.substr( start, end - start );
		}


#define FUNC_SIGNATURE_STRING                           \
	std::string_view                                    \
	{                                                   \
		std::source_location::current().function_name() \
	}

		template < typename Type >
		static consteval auto GetLongName() noexcept
		{
#if defined( __clang__ ) || defined( __GNUC__ )
			// Example GCC/Clang __PRETTY_FUNCTION__:
			// "consteval std::string_view detail::GetLongName() [with T = Foo]"
			constexpr std::string_view prefix = "T = ";
			constexpr std::string_view suffix = "]";
			return Extract( FUNC_SIGNATURE_STRING, prefix, suffix );

#elif defined( _MSC_VER )
			// Example MSVC __FUNCSIG__:
			// "consteval std::string_view __cdecl detail::GetLongName<struct Foo>(void)"
			constexpr std::string_view prefix1 = "GetLongName<";
			constexpr std::string_view prefix2 = "class ";
			constexpr std::string_view prefix3 = "struct ";
			constexpr std::string_view suffix = ">(void)";
			return Extract( Extract( Extract( FUNC_SIGNATURE_STRING, prefix1, suffix ), prefix2, {} ), prefix3, {} );
#endif
		}

		template < typename Type >
		static consteval auto GetName() noexcept
		{
			std::string_view long_name = GetLongName< Type >();
			auto first = long_name.find_last_of( "::" );
			if ( first == std::string_view::npos )
				first = long_name.find_last_of( ' ' ) + 1; // If npos, will wrap around to zero
			else
				first++;
			return long_name.substr( first, long_name.length() - first );
		}
	} // namespace detail

#define nameof( T ) ::iter8::detail::GetName< T >()


	inline std::string ToLower( std::string_view str )
	{
		return str | std::views::transform( []( char c ) -> char { return std::tolower( c ); } ) | std::ranges::to< std::string >();
	}

	namespace detail
	{
		template < typename E >
		concept MagicEnumFormattable = std::is_enum_v< E >;
	}

	template< detail::MagicEnumFormattable  T >
	struct EnumTraits
	{
		static constexpr bool UseStringFormat = true;
	};
} // namespace iter8

namespace std
{
	template < ::iter8::detail::MagicEnumFormattable E >
	struct formatter< E, char > : formatter< std::string_view, char >
	{
		template < typename FormatContext >
		auto format( E value, FormatContext& ctx ) const
		{
			if constexpr ( ::iter8::EnumTraits< E >::UseStringFormat )
			{
				std::string_view name = magic_enum::enum_name( value );
				if ( !name.empty() )
				{
					return formatter< std::string_view, char >::format( name, ctx );
				}
			}

			using U = std::underlying_type_t< E >;
			return formatter< U, char >{}.format( static_cast< U >( value ), ctx );
		}
	};
} // namespace std
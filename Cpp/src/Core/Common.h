#pragma once

#include "dpp/dpp.h"

#include <magic_enum/magic_enum.hpp>

#include <filesystem>
#include <source_location>

namespace iter8
{
	using TimePoint = std::chrono::time_point< std::chrono::system_clock >;

	inline double DurationToDouble( std::chrono::system_clock::duration d )
	{
		auto secs = std::chrono::duration_cast< std::chrono::duration< double > >( d );
		return secs.count();
	}

	inline double TimePointToDouble( TimePoint tp )
	{
		auto since_epoch = tp.time_since_epoch();
		return DurationToDouble( since_epoch );
	}

	static bool IS_LIVE = std::filesystem::exists( "/.dockerenv" );
	static bool IS_TESTING = not IS_LIVE;

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

		template < typename... Ts >
		struct AllSameImpl : std::false_type
		{};

		template < typename T >
		struct AllSameImpl< T > : std::true_type
		{};

		template < typename T, typename... Ts >
		struct AllSameImpl< T, Ts... >
			: std::conjunction< std::is_same< T, Ts >... >
		{};
	} // namespace detail

	template < typename... Ts >
	concept AllSame = detail::AllSameImpl< Ts... >::value;

	template < detail::MagicEnumFormattable T >
	struct EnumTraits
	{
		static constexpr bool UseStringFormat = true;
	};

	template < typename T >
	dpp::task< T > Result( dpp::async< dpp::confirmation_callback_t > const& awaitable )
	{
		auto result = co_await awaitable;
		co_return std::get< T >( result.value );
	}

	template < std::ranges::input_range R >
		requires std::same_as< std::ranges::range_value_t< R >, dpp::task< void > >
	dpp::task< void > AwaitAll( R&& tasks )
	{
		for ( auto& t : tasks )
		{
			co_await t;
		}
		co_return;
	}

	template < std::ranges::input_range R >
		requires std::same_as< std::ranges::range_value_t< R >, dpp::async< dpp::confirmation_callback_t > >
	dpp::task< void > AwaitAll( R&& tasks )
	{
		for ( auto t : tasks )
		{
			co_await t;
		}
		co_return;
	}

	namespace detail
	{
		template < typename T >
		T const& MinImpl( T const& v )
		{
			return v;
		}

		template < typename T, typename... Ts >
		T const& MinImpl( T const& v, Ts const&... vs )
		{
			T const m = MinImpl( vs... );
			return v < m ? v : m;
		}

		template < typename T >
		T const& MaxImpl( T const& v )
		{
			return v;
		}

		template < typename T, typename... Ts >
		T const& MaxImpl( T const& v, Ts const&... vs )
		{
			T const m = MaxImpl( vs... );
			return v > m ? v : m;
		}
	} // namespace detail

	template < typename T, typename... Ts >
		requires( std::convertible_to< T, Ts > and ... )
	T const& Min( T const& v, Ts const&... vs )
	{
		return detail::MinImpl( v, vs... );
	}

	template < typename T, typename... Ts >
		requires( std::convertible_to< T, Ts > and ... )
	T const& Max( T const& v, Ts const&... vs )
	{
		return detail::MaxImpl( v, vs... );
	}
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
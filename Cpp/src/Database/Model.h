#pragma once

#include "Core/Common.h"

#include "boost/pfr.hpp"

#include <type_traits>
#include <string>
#include <string_view>
#include <map>
#include <typeindex>

namespace iter8::db
{
	enum class ID : std::uint64_t
	{
		Zero = 0
	};

	namespace detail
	{
		template < typename T >
		struct is_time_point : std::false_type
		{};

		template < typename Clock, typename Duration >
		struct is_time_point< std::chrono::time_point< Clock, Duration > > : std::true_type
		{};

		template < typename T >
		inline constexpr bool is_time_point_v = is_time_point< std::remove_cv_t< T > >::value;

		template < typename T >
		struct is_blob_container : std::false_type
		{};

		template <>
		struct is_blob_container< std::vector< std::uint8_t > > : std::true_type
		{};

		template <>
		struct is_blob_container< std::vector< std::byte > > : std::true_type
		{};

		template < typename T >
		inline constexpr bool is_blob_container_v = is_blob_container< std::remove_cv_t< T > >::value;

		template < typename T >
		struct is_optional : std::false_type
		{};

		template < typename U >
		struct is_optional< std::optional< U > > : std::true_type
		{};

		template < typename T >
		inline constexpr bool is_optional_v =
			is_optional< std::remove_cv_t< std::remove_reference_t< T > > >::value;

		template < typename T >
		struct unwrap_optional_impl
		{
			using type = T;
		};

		template < typename U >
		struct unwrap_optional_impl< std::optional< U > >
		{
			using type = U;
		};

		template < typename T >
		using unwrap_optional_t = typename unwrap_optional_impl< T >::type;

		template < typename T, typename Target, std::size_t... Is >
		consteval bool HasFieldOfTypeImpl( std::index_sequence< Is... > )
		{
			return (
				// fold-expression over all field indices
				( std::is_same_v<
					  std::remove_cvref_t< decltype( boost::pfr::get< Is >( std::declval< T& >() ) ) >,
					  Target > ||
				  ... ) );
		}

		template < typename T, typename Target >
		constexpr bool HasFieldOfType =
			HasFieldOfTypeImpl< T, Target >(
				std::make_index_sequence< boost::pfr::tuple_size_v< T > >{} );

		inline std::string ToSnakeCase( std::string_view s )
		{
			std::string out;
			out.reserve( s.size() + s.size() / 4 ); // small heuristic

			bool prev_is_lower = false;

			for ( char c : s )
			{
				bool is_upper = std::isupper( static_cast< unsigned char >( c ) ) != 0;

				if ( is_upper )
				{
					if ( prev_is_lower )
					{
						out.push_back( '_' );
					}
					out.push_back( static_cast< char >( std::tolower( static_cast< unsigned char >( c ) ) ) );
				}
				else
				{
					out.push_back( c );
				}

				prev_is_lower = std::islower( static_cast< unsigned char >( c ) ) != 0;
			}

			return out;
		}

		template < typename T >
		std::string ToSnakeCase()
		{
			return ToSnakeCase( nameof( T ) );
		}

		inline std::chrono::system_clock::time_point ParseTimePoint( std::string_view s )
		{
			using sys_minutes = std::chrono::sys_time< std::chrono::minutes >; // matches %R (minutes precision)
			sys_minutes tp;

			std::istringstream iss( std::string{ s } );
			iss >> std::chrono::parse( "%FT%T%z", tp ); // same pattern as used in format

			if ( !iss )
				throw std::runtime_error( "Failed to parse time_point from: " + std::string{ s } );

			// convert to your desired precision (e.g. system_clock::time_point)
			return time_point_cast< std::chrono::system_clock::duration >( tp );
		}

		
	} // namespace detail

	template < typename T >
	static constexpr std::string_view GetSQLTypeMapping()
	{
		using U = std::remove_cv_t< std::remove_reference_t< T > >;

		if constexpr ( std::is_same_v< U, bool > )
		{
			return "BOOLEAN";
		}
		else if constexpr ( std::is_integral_v< U > or std::same_as< U, ID > )
		{
			return "INTEGER";
		}
		else if constexpr ( std::is_enum_v< U > )
		{
			return "ENUM";
		}
		else if constexpr ( std::is_floating_point_v< U > )
		{
			return "REAL";
		}
		else if constexpr ( std::is_same_v< U, std::string > ||
							std::is_same_v< U, std::string_view > ||
							std::is_same_v< U, char const* > ||
							std::is_same_v< U, char* > )
		{
			return "TEXT";
		}
		else if constexpr ( detail::is_blob_container_v< U > )
		{
			return "BLOB";
		}
		else if constexpr ( detail::is_time_point_v< U > )
		{
			return "DATETIME";
		}
		else
		{
			static_assert( false, "No SQL type mapping for this C++ type" );
		}
	}

	template < typename T >
	struct DbModelTraits
	{
		static constexpr bool IsSingleValued = !detail::HasFieldOfType< T, ID >;
		static inline auto const TableName = IsSingleValued ? detail::ToSnakeCase< T >() : std::format( "{}s", detail::ToSnakeCase< T >() );

		static constexpr auto ColumnNames = boost::pfr::names_as_array< T >();
	};

	template < typename T >
	concept DbModel = requires {
		{ DbModelTraits< T >::TableName } -> std::convertible_to< std::string_view >;
		DbModelTraits< T >::ColumnNames;
	};

	namespace detail
	{
		template < DbModel T, std::size_t... Is >
		std::string BuildCreateTableSqlImpl( std::index_sequence< Is... > )
		{
			using Traits = DbModelTraits< T >;
			constexpr auto& names = Traits::ColumnNames;

			std::ostringstream oss;

			oss << "CREATE TABLE IF NOT EXISTS " << Traits::TableName << " (\n";

			bool first = true;

			( (
				  [ & ] {
					  using FieldRaw = decltype( boost::pfr::get< Is >( std::declval< T& >() ) );
					  using Decayed = std::remove_cvref_t< FieldRaw >;
					  constexpr bool is_opt = detail::is_optional_v< Decayed >;
					  using Field = detail::unwrap_optional_t< Decayed >;

					  if ( !first )
						  oss << ",\n";
					  first = false;

					  std::string const col_name = ToSnakeCase( names[ Is ] );
					  std::string_view const type = GetSQLTypeMapping< Field >();

					  oss << "    " << col_name << ' ' << type;

					  if constexpr ( std::same_as< Field, ID > )
					  {
						  oss << " PRIMARY KEY";
					  }
					  else if constexpr ( !is_opt )
					  {
						  oss << " NOT NULL";
					  }
				  }() ),
			  ... );

			oss << "\n);";

			return oss.str();
		}
	} // namespace detail

	template < DbModel T >
	std::string BuildCreateTableSql()
	{
		constexpr std::size_t n = boost::pfr::tuple_size_v< T >;
		return detail::BuildCreateTableSqlImpl< T >( std::make_index_sequence< n >{} );
	}
} // namespace iter8::db
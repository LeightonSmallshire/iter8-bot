#pragma once

#include "Model.h"

#include <magic_enum/magic_enum.hpp>

namespace iter8::db
{
	using SqlValue = std::variant< std::monostate, bool, std::int64_t, double, std::string >;

	enum class Cmp
	{
		Eq,
		Is,
		IsNot,
		Lt,
		Le,
		Gt,
		Ge,
	};

	enum class Ordering
	{
		Asc,
		Desc,
	};

	template < DbModel T, typename Field >
	struct WhereParam
	{
		Field T::* field;
		Field const& value;
		Cmp cmp{ Cmp::Eq };
	};

	template < DbModel T, typename Field >
	struct OrderParam
	{
		Field T::* field;
		Ordering dir;
	};

	namespace detail
	{
		template < DbModel T >
		struct WhereParamImpl
		{
			int column_index;
			Cmp cmp;
			SqlValue value;
		};

		template < DbModel T >
		struct OrderParamImpl
		{
			int column_index;
			Ordering dir;
		};


		template < typename T, typename Field >
		int FieldIndex( Field T::* member )
		{
			T tmp{};

			int result = -1;
			int idx = 0;
			boost::pfr::for_each_field( tmp, [ & ]( auto& f ) {
				auto lhs = static_cast< void* >( std::addressof( f ) );
				auto rhs = static_cast< void* >( std::addressof( tmp.*member ) );
				if ( lhs == rhs )
				{
					result = idx;
				}
				++idx;
			} );

			if ( result == -1 )
			{
				throw std::logic_error( "FieldIndex: member not found in DbModel" );
			}

			return result;
		}

		template < typename U >
		SqlValue ToSqlValue( U const& field )
		{
			using T = std::remove_cvref_t< U >;

			if constexpr ( detail::is_optional_v< T > )
			{
				if ( !field )
				{
					return SqlValue{ std::monostate{} }; // NULL
				}
				return ToSqlValue( *field );
			}
			else if constexpr ( std::is_same_v< T, bool > )
			{
				return SqlValue{ field };
			}
			else if constexpr ( std::is_integral_v< T > or std::same_as< ID, T > )
			{
				return SqlValue{ static_cast< std::int64_t >( field ) };
			}
			else if constexpr ( std::is_floating_point_v< T > )
			{
				return SqlValue{ static_cast< double >( field ) };
			}
			else if constexpr ( std::is_enum_v< T > )
			{
				auto enum_str = magic_enum::enum_name( field );
				return SqlValue{ std::string{ enum_str } };
			}
			else if constexpr (detail::is_time_point_v< U >)
			{
				auto tp_str = std::format( "{0:%F}T{0:%T%z}", field );
				return SqlValue{ tp_str };
			}
			else if constexpr ( std::is_same_v< T, std::string > )
			{
				return SqlValue{ field };
			}
			else
			{
				static_assert( std::is_same_v< T, void >, "Unsupported field type for ToSqlValue" );
			}
		}

		template < DbModel T, typename Field >
		WhereParamImpl< T > MakeWhereImpl( WhereParam< T, Field > const& p )
		{
			return WhereParamImpl< T >{
				.column_index = FieldIndex( p.field ),
				.cmp = p.cmp,
				.value = ToSqlValue( p.value ),
			};
		}

		template < DbModel T, typename Field >
		OrderParamImpl< T > MakeOrderImpl( OrderParam< T, Field > const& p )
		{
			return OrderParamImpl< T >{
				.column_index = FieldIndex( p.field ),
				.dir = p.dir,
			};
		}
	} // namespace detail

	template < DbModel T >
	using WhereClause = std::vector< detail::WhereParamImpl< T > >;

	template < DbModel T >
	using OrderByClause = std::vector< detail::OrderParamImpl< T > >;

	template < DbModel T, typename... Fields >
	WhereClause< T > Where( WhereParam< T, Fields > const&... params )
	{
		WhereClause< T > clause;
		clause.reserve( sizeof...( Fields ) );
		( clause.push_back( detail::MakeWhereImpl( params ) ), ... );
		return clause;
	}

	template < DbModel T, typename... Fields >
	OrderByClause< T > OrderBy( OrderParam< T, Fields > const&... params )
	{
		OrderByClause< T > clause;
		clause.reserve( sizeof...( Fields ) );
		( clause.push_back( detail::MakeOrderImpl( params ) ), ... );
		return clause;
	}
}
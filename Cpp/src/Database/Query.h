#pragma once

#include "Model.h"

namespace iter8::db
{
	using SqlValue = std::variant< std::monostate, bool, std::int64_t, double, std::string >;

	enum class CmpOp
	{
		Eq,
		Is,
		IsNot,
		Lt,
		Le,
		Gt,
		Ge,
	};

	enum class OrderDir
	{
		Asc,
		Desc,
	};

	template < DbModel T, typename Field >
	struct WhereParam
	{
		Field T::* field;
		Field const& value;
		CmpOp cmp;
	};

	template < DbModel T, typename Field >
	struct OrderParam
	{
		Field T::* field;
		OrderDir dir;
	};

	namespace detail
	{
		template < DbModel T >
		struct WhereParamImpl
		{
			int column_index;
			CmpOp cmp;
			SqlValue value;
		};

		template < DbModel T >
		struct OrderParamImpl
		{
			int column_index;
			OrderDir dir;
		};


		template < typename T, typename Field >
		int FieldIndex( Field T::* member )
		{
			T tmp{};

			int result = -1;
			int idx = 0;
			boost::pfr::for_each_field( tmp, [ & ]( auto& f ) {
				if ( std::addressof( f ) == std::addressof( tmp.*member ) )
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
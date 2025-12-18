#pragma once

#include "Model.h"

#include "Core/Reflection.h"

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

	enum class JoinType
	{
		Inner,
		Left,
		Right,
		Full
	};

	namespace detail
	{
		template < DbModel T, typename Field >
		struct WhereParam
		{
			Field T::* field;
			Field value;
			Cmp cmp{ Cmp::Eq };
		};

		template < DbModel T, typename Field >
		struct OrderParam
		{
			Field T::* field;
			Ordering dir;
		};

		template < DbModel T, typename Field >
			requires detail::is_foreign_key_v< Field >
		struct JoinParam
		{
			Field T::* fk;
			JoinType join;
		};
	} // namespace detail

	template < typename T, typename Field, typename V >
		requires std::constructible_from< Field, V >
	auto Param( Field T::* field, V&& v, Cmp cmp = Cmp::Eq ) -> detail::WhereParam< T, Field >
	{
		return detail::WhereParam< T, Field >{ field, v, cmp };
	}

	template < typename T, typename Field >
	auto Param( Field T::* field, Ordering o ) -> detail::OrderParam< T, Field >
	{
		return detail::OrderParam< T, Field >{ field, o };
	}

	template < typename T, typename Field >
		requires detail::is_foreign_key_v< Field >
	auto Param( Field T::* field, JoinType j ) -> detail::JoinParam< T, Field >
	{
		return detail::JoinParam< T, Field >{ field, j };
	}

	namespace detail
	{
		struct WhereParamImpl
		{
			int column_index;
			Cmp cmp;
			SqlValue value;
		};

		struct OrderParamImpl
		{
			int column_index;
			Ordering dir;
		};

		struct JoinParamImpl
		{
			std::type_index owner;
			std::type_index target;
			int owner_fk_column_index{};
			int target_key_column_index{};
			JoinType join{};
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
			else if constexpr ( is_foreign_key_v< T > )
			{
				return SqlValue{ static_cast< std::int64_t >( field.value ) };
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
			else if constexpr ( detail::is_time_point_v< U > )
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
		WhereParamImpl MakeWhereImpl( WhereParam< T, Field > const& p )
		{
			return WhereParamImpl{
				.column_index = FieldIndex( p.field ),
				.cmp = p.cmp,
				.value = ToSqlValue( p.value ),
			};
		}

		template < DbModel T, typename Field >
		OrderParamImpl MakeOrderImpl( OrderParam< T, Field > const& p )
		{
			return OrderParamImpl{
				.column_index = FieldIndex( p.field ),
				.dir = p.dir,
			};
		}

		template < DbModel T, typename Field >
		JoinParamImpl MakeJoinImpl( JoinParam< T, Field > const& p )
		{
			using Target = typename foreign_key_target< Field >::model_type;

			return JoinParamImpl{
				.owner = typeid( T ),
				.target = typeid( Target ),
				.owner_fk_column_index = FieldIndex( p.fk ),
				.target_key_column_index = FieldIndex( Field::field ),
				.join = p.join,
			};
		}

		inline char const* ToSqlJoin( JoinType j )
		{
			switch ( j )
			{
				case JoinType::Inner:
					return "JOIN";
				case JoinType::Left:
					return "LEFT JOIN";
				case JoinType::Right:
					return "RIGHT JOIN";
				case JoinType::Full:
					return "FULL JOIN";
			}
			return "JOIN";
		}
	} // namespace detail

	using WhereClause = std::vector< detail::WhereParamImpl >;
	using OrderByClause = std::vector< detail::OrderParamImpl >;
	using JoinClause = std::vector< detail::JoinParamImpl >;

	template < DbModel T, typename... Fields >
	WhereClause Where( detail::WhereParam< T, Fields > const&... params )
	{
		WhereClause clause;
		clause.reserve( sizeof...( Fields ) );
		( clause.push_back( detail::MakeWhereImpl( params ) ), ... );
		return clause;
	}

	template < DbModel T, typename... Fields >
	OrderByClause OrderBy( detail::OrderParam< T, Fields > const&... params )
	{
		OrderByClause clause;
		clause.reserve( sizeof...( Fields ) );
		( clause.push_back( detail::MakeOrderImpl( params ) ), ... );
		return clause;
	}

	template < DbModel T, typename... Fields >
	JoinClause On( detail::JoinParam< T, Fields > const&... params )
	{
		JoinClause clause;
		clause.reserve( sizeof...( Fields ) );
		( clause.push_back( detail::MakeJoinImpl( params ) ), ... );
		return clause;
	}

	namespace detail
	{
		template < typename Tuple >
		struct TypeIndexOf;

		template < typename... Ts >
		struct TypeIndexOf< std::tuple< Ts... > >
		{
			static std::optional< std::size_t > Find( std::type_index ti )
			{
				std::optional< std::size_t > out{};
				std::size_t idx = 0;

				auto check = [ & ]( auto tag ) {
					using T = std::remove_cvref_t< decltype( tag ) >;
					if ( !out && ti == typeid( T ) )
						out = idx;
					++idx;
				};

				( check( Ts{} ), ... );

				return out;
			}
		};

		template < DbModel From, DbModel Target >
		consteval std::size_t CountFkTo()
		{
			constexpr std::size_t N = boost::pfr::tuple_size_v< From >;
			std::size_t c = 0;
			[ & ]< std::size_t... I >( std::index_sequence< I... > ) {
				( ( [ & ] {
					  using Field = std::remove_cvref_t< boost::pfr::tuple_element_t< I, From > >;
					  if constexpr ( is_foreign_key_v< Field > )
					  {
						  using Ref = typename foreign_key_target< Field >::model_type;
						  if constexpr ( std::same_as< Ref, Target > )
							  ++c;
					  }
				  }() ),
				  ... );
			}( std::make_index_sequence< N >{} );
			return c;
		}

		template < DbModel A, DbModel B >
		consteval bool HasAnyFkEitherWay()
		{
			return ( CountFkTo< A, B >() > 0 ) || ( CountFkTo< B, A >() > 0 );
		}

		template < typename Tuple, std::size_t I >
		consteval bool HasConnectionToEarlier()
		{
			static_assert( I > 0 );
			bool ok = false;

			[ & ]< std::size_t... J >( std::index_sequence< J... > ) {
				( ( [ & ] {
					  using Cur = std::tuple_element_t< I, Tuple >;
					  using Prev = std::tuple_element_t< J, Tuple >;
					  if constexpr ( HasAnyFkEitherWay< Cur, Prev >() )
						  ok = true;
				  }() ),
				  ... );
			}( std::make_index_sequence< I >{} );

			return ok;
		}

		template < typename Tuple >
		consteval bool ValidateJoinPack()
		{
			bool ok = true;
			[ & ]< std::size_t... I >( std::index_sequence< I... > ) {
				( ( [ & ] {
					  if constexpr ( I == 0 )
						  return;
					  else if constexpr ( !HasConnectionToEarlier< Tuple, I >() )
						  ok = false;
				  }() ),
				  ... );
			}( std::make_index_sequence< std::tuple_size< Tuple >::value >{} );
			return ok;
		}

		template < typename Tuple >
		void ValidateJoinPackOrThrow()
		{
			static_assert( ValidateJoinPack< Tuple >(),
						   "JoinSelect: one of the provided models has no ForeignKey relationship to any earlier model in the pack" );
		}

		struct JoinEdgeRuntime
		{
			std::size_t left{};
			std::size_t right{};
			std::size_t owner{};
			int owner_fk_col{};
			int target_key_col{};
			JoinType join{};
		};

		inline std::optional< JoinEdgeRuntime > TryEdgeFromJoinClause(
			std::size_t cur_index,
			std::type_index cur_type,
			JoinClause const& clause,
			std::vector< bool >& used,
			std::size_t left_index,
			std::type_index left_type )
		{
			for ( std::size_t k = 0; k < clause.size(); ++k )
			{
				if ( used[ k ] )
					continue;

				auto const& j = clause[ k ];

				bool const matches_cur_left =
					( j.owner == cur_type && j.target == left_type ) ||
					( j.owner == left_type && j.target == cur_type );

				if ( !matches_cur_left )
					continue;

				JoinEdgeRuntime e{};
				e.left = left_index;
				e.right = cur_index;

				if ( j.owner == cur_type )
				{
					e.owner = cur_index;
					e.owner_fk_col = j.owner_fk_column_index;
					e.target_key_col = j.target_key_column_index;
				}
				else
				{
					e.owner = left_index;
					e.owner_fk_col = j.owner_fk_column_index;
					e.target_key_col = j.target_key_column_index;
				}

				e.join = j.join;

				used[ k ] = true; // consume this join param
				return e;
			}

			return {};
		}

		template < typename Tuple, std::size_t CurI >
		JoinEdgeRuntime FindJoinEdgeImpl( JoinClause const& clause, std::vector< bool >& used )
		{
			using Cur = std::tuple_element_t< CurI, Tuple >;

			std::optional< JoinEdgeRuntime > found{};

			[ & ]< std::size_t... J >( std::index_sequence< J... > ) {
				( ( [ & ] {
					  using L = std::tuple_element_t< J, Tuple >;

					  auto cur_ti = std::type_index( typeid( Cur ) );
					  auto left_ti = std::type_index( typeid( L ) );

					  if ( auto e = TryEdgeFromJoinClause( CurI, cur_ti, clause, used, J, left_ti ) )
					  {
						  if ( found )
							  throw std::logic_error( "JoinSelect: multiple join clauses matched for one join; ambiguous" );
						  found = *e;
					  }
				  }() ),
				  ... );
			}( std::make_index_sequence< CurI >{} );

			if ( found )
				return *found;

			// inference path unchanged; keep your existing inference logic here if you want it.
			throw std::logic_error( "JoinSelect: no join edge found (provide On(...))" );
		}

		template < DbModel From, DbModel To >
		inline int FindUniqueFkFieldIndex()
		{
			constexpr std::size_t N = boost::pfr::tuple_size_v< From >;
			int idx = -1;
			int count = 0;

			From tmp{};
			int i = 0;
			boost::pfr::for_each_field( tmp, [ & ]( auto& f ) {
				using Field = std::remove_cvref_t< decltype( f ) >;
				if constexpr ( is_foreign_key_v< Field > )
				{
					using Ref = typename foreign_key_target< Field >::model_type;
					if constexpr ( std::same_as< Ref, To > )
					{
						++count;
						idx = i;
					}
				}
				++i;
			} );

			if ( count != 1 )
				throw std::logic_error( "JoinSelect: FK not unique; provide On(...)" );

			return idx;
		}

		template < DbModel From, DbModel To >
		inline int FindReferencedKeyIndexFromFk( int from_fk_index )
		{
			From tmp{};
			int i = 0;
			int out = -1;

			boost::pfr::for_each_field( tmp, [ & ]( auto& f ) {
				if ( i == from_fk_index )
				{
					using Field = std::remove_cvref_t< decltype( f ) >;
					out = FieldIndex( Field::field );
				}
				++i;
			} );

			if ( out < 0 )
				throw std::logic_error( "JoinSelect: failed to compute referenced key index" );

			return out;
		}

		template < typename Tuple >
		JoinEdgeRuntime FindJoinEdge( std::size_t cur_index, JoinClause const& clause, std::vector< bool >& used )
		{
			JoinEdgeRuntime e{};
			bool set = false;

			[ & ]< std::size_t... I >( std::index_sequence< I... > ) {
				( ( [ & ] {
					  if constexpr ( I == 0 )
						  return;

					  if ( I == cur_index )
					  {
						  e = FindJoinEdgeImpl< Tuple, I >( clause, used );
						  set = true;
					  }
				  }() ),
				  ... );
			}( std::make_index_sequence< std::tuple_size_v< Tuple > >{} );

			if ( !set )
				throw std::logic_error( "JoinSelect: invalid join index" );

			return e;
		}

		inline void AppendJoinCondition( std::ostringstream& oss, JoinEdgeRuntime const& e )
		{
			std::size_t const owner = e.owner;
			std::size_t const other = ( owner == e.right ? e.left : e.right );

			oss << "t" << owner << '.'
				<< "t" << owner << '_' << "dummy";																 // overwritten below
			oss.seekp( -static_cast< std::streamoff >( std::string( "tX_dummy" ).size() ), std::ios_base::cur ); // overwritten below
		}

		template < DbModel M >
		inline void AppendSelectListFor( std::ostringstream& oss, std::size_t alias, bool& first )
		{
			constexpr auto& names = DbModelTraits< M >::ColumnNames;

			for ( std::size_t c = 0; c < names.size(); ++c )
			{
				if ( !first )
					oss << ", ";
				first = false;

				auto col = ToSnakeCase( names[ c ] );
				oss << "t" << alias << '.' << col
					<< " AS t" << alias << '_' << col;
			}
		}

		template < typename Tuple >
		void AppendSelectList( std::ostringstream& oss, bool& first )
		{
			[ & ]< std::size_t... I >( std::index_sequence< I... > ) {
				( ( AppendSelectListFor< std::tuple_element_t< I, Tuple > >( oss, I, first ) ), ... );
			}( std::make_index_sequence< std::tuple_size< Tuple >::value >{} );
		}

		template < typename Tuple, std::size_t I >
		std::string ColumnNameAt( int col_index )
		{
			using M = std::tuple_element_t< I, Tuple >;
			constexpr auto& names = DbModelTraits< M >::ColumnNames;
			return ToSnakeCase( names[ static_cast< std::size_t >( col_index ) ] );
		}

		inline void AppendJoinCondition( std::ostringstream& oss, JoinEdgeRuntime const& e, std::function< std::string( std::size_t, int ) > const& colname )
		{
			std::size_t const owner = e.owner;
			std::size_t const other = ( owner == e.right ? e.left : e.right );

			oss << "t" << owner << '.' << colname( owner, e.owner_fk_col )
				<< " = "
				<< "t" << other << '.' << colname( other, e.target_key_col );
		}

		template < typename Tuple >
		void AppendJoinCondition( std::ostringstream& oss, JoinEdgeRuntime const& e )
		{
			auto colname = [ & ]( std::size_t table, int col ) -> std::string {
				std::string out{};
				bool set = false;

				[ & ]< std::size_t... I >( std::index_sequence< I... > ) {
					( ( [ & ] {
						  if ( set )
							  return;
						  if ( table == I )
						  {
							  out = ColumnNameAt< Tuple, I >( col );
							  set = true;
						  }
					  }() ),
					  ... );
				}( std::make_index_sequence< std::tuple_size< Tuple >::value >{} );

				if ( !set )
					throw std::logic_error( "JoinSelect: invalid table index" );
				return out;
			};

			AppendJoinCondition( oss, e, colname );
		}
	} // namespace detail
} // namespace iter8::db
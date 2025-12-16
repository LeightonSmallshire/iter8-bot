#pragma once

#include "Model.h"
#include "Query.h"
#include "Statement.h"
#include "Transaction.h"

#include "Logging/Log.h"

#include <sqlite3.h>

#include <magic_enum/magic_enum.hpp>

#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>
#include <concepts>
#include <ranges>

namespace iter8::db
{
	struct SqliteError : std::runtime_error
	{
		using std::runtime_error::runtime_error;
	};

	/// Database connection class used for executing commands on the DB.
	///		Init 				Initialise a table for a given model type. Optional drop a possibly existing table.
	///		Select 				SQL SELECT for a model type. Optional Where and OrderBy clauses.
	///							Returns DbCursor which is iterable and will lazily retrieve the next row as it iterates. Use `ReadAll` on the cursor to fully evaluate.
	///		SelectOne			Select but only returns the first result in a std::optional. 
	///		Update				SQL UPDATE any rows that matches the record provided. If the model type as an ID column it will automatically match that record.
	///							Optional Where clause
	///		Delete				SQL DELETE for a model type. Optional Where clause.
	///		InsertRange			SQL INSERT for a range that contains a model type.
	///		Insert				Same as InsertRange but using variadic arguments
	///		InsertOrUpdate		Insert if no record exists, Update otherwise
	///		JoinSelect			Select but joining across two or more model tables. Optional Where and OrderBy clauses
	///							Will automatically match searching for a ForeignKey on one of the model types. If a model contains more than one ForeignKey
	///							then use an On clause to specify the join.
	///		JoinSelectOne		JoinSelect but only returns the first result in a std::optional. 
	///		ExecRaw				Execute a raw string query. Any results returned as a formatted table string
	///		BeginTransaciton	Begin a transaction. Returns a RAII encapsulated object for managing the transaction 
	///							which automatically rollbacks on destruction if you don't explicitly commit.
	class Connection
	{
	public:
		Connection( std::string_view path );
		~Connection();

		Connection( Connection&& other ) noexcept;
		Connection& operator=( Connection&& other ) noexcept;

	public:
		template < typename T >
		class DbCursor
		{
		public:
			struct iterator
			{
				enum class Stage
				{
					NotStarted,
					InProgress,
					Complete
				};

				using iterator_category = std::input_iterator_tag;
				using value_type = T;
				using difference_type = std::ptrdiff_t;

				Connection* db{ nullptr };
				Statement* stmt;
				std::optional< T > current{};
				Stage stage{ Stage::NotStarted };

				iterator() = default;
				explicit iterator( Connection* ctx, Statement& statement )
					: db( ctx ), stmt( &statement )
				{
					advance();
				}

				T const& operator*() const
				{
					return current.value();
				}

				T const* operator->() const
				{
					return &current.value();
				}

				iterator& operator++()
				{
					advance();
					return *this;
				}

				void operator++( int )
				{
					advance();
				}

				bool operator==( iterator const& other ) const
				{
					return db == other.db and stmt == other.stmt and stage == other.stage and current == other.current;
				}

				bool operator!=( iterator const& other ) const
				{
					return !( *this == other );
				}

				friend bool operator==( iterator const& it, std::default_sentinel_t ) noexcept
				{
					return it.stage == Stage::Complete;
				}

				friend bool operator!=( iterator const& it, std::default_sentinel_t s ) noexcept
				{
					return !( it == s );
				}

				friend bool operator==( std::default_sentinel_t s, iterator const& it ) noexcept
				{
					return it == s;
				}

				friend bool operator!=( std::default_sentinel_t s, iterator const& it ) noexcept
				{
					return !( s == it );
				}

			private:
				void advance()
				{
					if ( stage == Stage::Complete )
						return;

					stage = Stage::InProgress;

					// Step once
					if ( db->Step( *stmt ) )
					{
						db->ReadRowInto( *stmt, current );
					}
					else
					{
						current = {};
						stage = Stage::Complete;
					}
				}
			};

			explicit DbCursor( Connection* db, Statement stmt )
				: db_{ db }, statement_{ std::move( stmt ) }
			{}

			friend iterator begin( DbCursor& c )
			{
				return iterator{ c.db_, c.statement_ };
			}

			friend std::default_sentinel_t end( DbCursor& c ) noexcept
			{
				return {};
			}

			std::vector< T > ReadAll()
			{
				return std::ranges::to< std::vector >( *this );
			}

			Statement& GetStatement()
			{
				return statement_;
			}

		private:
			Connection* db_;
			Statement statement_;
		};

	public:
		template < typename T >
		void Init( bool truncate )
		{
			if ( truncate )
				Exec( std::format( "DROP TABLE IF EXISTS {}", DbModelTraits< T >::TableName ) );

			auto sql = BuildCreateTableSql< T >();
			Exec( sql );
		}

		template < typename T >
		DbCursor< T > Select( WhereClause const& where = {}, OrderByClause const& order_by = {} )
		{
			using Traits = DbModelTraits< T >;
			constexpr auto& names = Traits::ColumnNames;

			std::ostringstream oss;
			oss << "SELECT ";

			for ( std::size_t i = 0; i < names.size(); ++i )
			{
				if ( i > 0 )
					oss << ", ";
				oss << detail::ToSnakeCase( names[ i ] );
			}

			oss << " FROM " << Traits::TableName;

			if ( !where.empty() )
			{
				oss << " WHERE ";
				for ( std::size_t i = 0; i < where.size(); ++i )
				{
					if ( i > 0 )
						oss << " AND ";

					auto const& w = where[ i ];
					oss << detail::ToSnakeCase( names[ static_cast< std::size_t >( w.column_index ) ] )
						<< ' ' << ToSqlOp( w.cmp ) << " ?";
				}
			}

			if ( !order_by.empty() )
			{
				oss << " ORDER BY ";
				for ( std::size_t i = 0; i < order_by.size(); ++i )
				{
					if ( i > 0 )
						oss << ", ";

					auto const& o = order_by[ i ];
					oss << detail::ToSnakeCase( names[ static_cast< std::size_t >( o.column_index ) ] )
						<< ( o.dir == Ordering::Desc ? " DESC" : " ASC" );
				}
			}

			oss << ';';

			Statement stmt = Prepare( oss.view() );

			int param_index = 1;
			for ( auto const& w : where )
			{
				BindSqlValue( stmt, param_index++, w.value );
			}

			return DbCursor< T >{ this, std::move( stmt ) };
		}

		template < typename T >
		std::optional< T > SelectOne( WhereClause const& where = {}, OrderByClause const& order_by = {} )
		{
			using Traits = DbModelTraits< T >;
			constexpr auto& names = Traits::ColumnNames;

			std::ostringstream oss;
			oss << "SELECT ";

			for ( std::size_t i = 0; i < names.size(); ++i )
			{
				if ( i > 0 )
					oss << ", ";
				oss << detail::ToSnakeCase( names[ i ] );
			}

			oss << " FROM " << Traits::TableName;

			if ( !where.empty() )
			{
				oss << " WHERE ";
				for ( std::size_t i = 0; i < where.size(); ++i )
				{
					if ( i > 0 )
						oss << " AND ";

					auto const& w = where[ i ];
					oss << detail::ToSnakeCase( names[ static_cast< std::size_t >( w.column_index ) ] )
						<< ' ' << ToSqlOp( w.cmp ) << " ?";
				}
			}

			if ( !order_by.empty() )
			{
				oss << " ORDER BY ";
				for ( std::size_t i = 0; i < order_by.size(); ++i )
				{
					if ( i > 0 )
						oss << ", ";

					auto const& o = order_by[ i ];
					oss << detail::ToSnakeCase( names[ static_cast< std::size_t >( o.column_index ) ] )
						<< ( o.dir == Ordering::Desc ? " DESC" : " ASC" );
				}
			}

			oss << ';';

			Statement stmt = Prepare( oss.view() );

			int param_index = 1;
			for ( auto const& w : where )
			{
				BindSqlValue( stmt, param_index++, w.value );
			}

			if ( not Step( stmt ) )
				return {};

			std::optional< T > result;
			ReadRowInto( stmt, result );

			return result;
		}

		template < typename T >
		void Update( T const& data, WhereClause const& where = {} )
		{
			using Traits = DbModelTraits< T >;
			constexpr auto& names = Traits::ColumnNames;
			static_assert( !names.empty(), "DbModelTraits::ColumnNames must not be empty" );

			if constexpr ( not Traits::IsSingleValued )
			{
				if ( data.id == ID::Zero )
				{
					log::Error( "Attempting to update a record with a zero ID" );
					throw std::logic_error( "Attempting to update a record with a zero ID" );
				}
			}

			std::ostringstream oss;
			oss << "UPDATE " << Traits::TableName << " SET ";

			bool first = true;
			for ( std::size_t i = 0; i < names.size(); ++i )
			{
				if ( !first )
					oss << ", ";
				first = false;
				oss << detail::ToSnakeCase( names[ i ] ) << " = ?";
			}

			if constexpr ( not Traits::IsSingleValued )
			{
				oss << " WHERE id = ? ";
			}

			if ( !where.empty() )
			{
				if constexpr ( Traits::IsSingleValued )
				{
					oss << " WHERE ";
				}

				for ( std::size_t i = 0; i < where.size(); ++i )
				{
					if ( i > 0 )
						oss << " AND ";
					auto const& w = where[ i ];
					oss << detail::ToSnakeCase( names[ static_cast< std::size_t >( w.column_index ) ] )
						<< ' ' << ToSqlOp( w.cmp ) << " ?";
				}
			}

			oss << ';';

			Statement stmt = Prepare( oss.view() );

			// Bind all fields from 'data' first.
			int param_index = 1;
			boost::pfr::for_each_field( data, [ & ]( auto const& field ) {
				BindOne( stmt, param_index, field );
			} );

			// Then WHERE values.
			if constexpr ( not Traits::IsSingleValued )
			{
				BindOne( stmt, param_index, data.id );
			}

			for ( auto const& w : where )
			{
				BindSqlValue( stmt, param_index++, w.value );
			}

			StepOnce( stmt );
		}

		template < typename T >
		void Delete( WhereClause const& where = {} )
		{
			using Traits = DbModelTraits< T >;
			constexpr auto& names = Traits::ColumnNames;

			std::ostringstream oss;
			oss << "DELETE FROM " << Traits::TableName;

			if ( !where.empty() )
			{
				oss << " WHERE ";
				for ( std::size_t i = 0; i < where.size(); ++i )
				{
					if ( i > 0 )
						oss << " AND ";
					auto const& w = where[ i ];
					oss << detail::ToSnakeCase( names[ static_cast< std::size_t >( w.column_index ) ] )
						<< ' ' << ToSqlOp( w.cmp ) << " ?";
				}
			}

			oss << ';';

			Statement stmt = Prepare( oss.view() );

			int param_index = 1;
			for ( auto const& w : where )
			{
				BindSqlValue( stmt, param_index++, w.value );
			}

			StepOnce( stmt );
		}

		template < typename T >
		static int HasId( T const& t )
		{
			using Traits = DbModelTraits< T >;
			if constexpr ( Traits::IsSingleValued )
			{
				return false;
			}
			else
			{
				return boost::pfr::get< 0 >( t ) != ID::Zero;
			}
		}


		template < typename T >
		static int StartIndex( T const& t )
		{
			using Traits = DbModelTraits< T >;
			if constexpr ( Traits::IsSingleValued )
			{
				return 0;
			}
			else
			{
				return boost::pfr::get< 0 >( t ) != ID::Zero ? 0 : 1;
			}
		}

		template < std::ranges::input_range range_t, typename T = std::ranges::range_value_t< range_t > >
			requires DbModel< std::remove_cvref_t< T > >
		void InsertRange( range_t&& data )
		{
			if ( data.empty() )
				return;

			using Traits = DbModelTraits< T >;
			constexpr auto& names = Traits::ColumnNames;

			bool has_id = HasId( data.front() );
			auto start_index = StartIndex( data.front() );

			std::ostringstream oss;
			oss << "INSERT INTO " << Traits::TableName << " (";

			for ( std::size_t i = start_index; i < names.size(); ++i )
			{
				if ( i > start_index )
					oss << ", ";
				oss << detail::ToSnakeCase( names[ i ] );
			}

			oss << ") VALUES (";

			for ( std::size_t i = start_index; i < names.size(); ++i )
			{
				if ( i > start_index )
					oss << ", ";
				oss << '?';
			}

			oss << ")";

			if ( has_id )
			{
				oss << " ON CONFLICT(id) DO NOTHING";
			}

			oss << ";";

			Statement stmt = Prepare( oss.view() );

			for ( auto&& elem : data )
			{
				int param_index = 1;
				boost::pfr::for_each_field( elem, [ & ]( auto const& field ) {
					BindOne( stmt, param_index, field );
				} );

				StepOnce( stmt );
			}
		}

		template < DbModel... Ts >
			requires( sizeof...( Ts ) > 0 ) && AllSame< Ts... >
		void Insert( Ts const&... ts )
		{
			InsertRange( std::array{ ts... } );
		}

		template < DbModel T >
		void InsertOrUpdate( T const& value )
		{
			if constexpr ( DbModelTraits< T >::IsSingleValued )
			{
				if ( SelectOne< T >() )
					Update( value );
				else
					Insert( value );
			}
			else
			{
				if ( SelectOne< T >( Where( WhereParam( &T::id, value.id ) ) ) )
					Update( value );
				else
					Insert( value );
			}
		}

		template < DbModel... T >
		DbCursor< std::tuple< T... > > JoinSelect(
			JoinClause const& join = {},
			WhereClause const& where = {},
			OrderByClause const& order_by = {} )
		{
			static_assert( sizeof...( T ) >= 2, "JoinSelect requires at least 2 models" );

			using TupleT = std::tuple< T... >;

			detail::ValidateJoinPackOrThrow< TupleT >();

			std::ostringstream oss;
			oss << "SELECT ";

			bool first_sel = true;
			detail::AppendSelectList< TupleT >( oss, first_sel );

			using First = std::tuple_element_t< 0, TupleT >;
			oss << " FROM " << DbModelTraits< First >::TableName << " AS t0";

			std::vector< bool > used( join.size(), false );

			[ & ]< std::size_t... I >( std::index_sequence< I... > ) {
				( ( [ & ] {
					  if constexpr ( I == 0 )
						  return;

					  using Cur = std::tuple_element_t< I, TupleT >;

					  auto edge = detail::FindJoinEdge< TupleT >( I, join, used );

					  oss << ' ' << detail::ToSqlJoin( edge.join ) << ' '
						  << DbModelTraits< Cur >::TableName << " AS t" << I
						  << " ON ";

					  detail::AppendJoinCondition< TupleT >( oss, edge );
				  }() ),
				  ... );
			}( std::make_index_sequence< sizeof...( T ) >{} );

			if ( !where.empty() )
			{
				constexpr auto& names = DbModelTraits< First >::ColumnNames;

				oss << " WHERE ";
				for ( std::size_t i = 0; i < where.size(); ++i )
				{
					if ( i > 0 )
						oss << " AND ";
					auto const& w = where[ i ];
					oss << "t0." << detail::ToSnakeCase( names[ static_cast< std::size_t >( w.column_index ) ] )
						<< ' ' << ToSqlOp( w.cmp ) << " ?";
				}
			}

			if ( !order_by.empty() )
			{
				constexpr auto& names = DbModelTraits< First >::ColumnNames;

				oss << " ORDER BY ";
				for ( std::size_t i = 0; i < order_by.size(); ++i )
				{
					if ( i > 0 )
						oss << ", ";
					auto const& o = order_by[ i ];
					oss << "t0." << detail::ToSnakeCase( names[ static_cast< std::size_t >( o.column_index ) ] )
						<< ( o.dir == Ordering::Desc ? " DESC" : " ASC" );
				}
			}

			oss << ';';

			Statement stmt = Prepare( oss.view() );

			int param_index = 1;
			for ( auto const& w : where )
				BindSqlValue( stmt, param_index++, w.value );

			return DbCursor< std::tuple< T... > >{ this, std::move( stmt ) };
		}

		template < DbModel... T >
		std::optional< std::tuple< T... > > JoinSelectOne(
			JoinClause const join_type = {},
			WhereClause const& where = {},
			OrderByClause const& order_by = {} )
		{
			auto cursor = JoinSelect< T... >( std::move( join_type ), where, order_by );
			auto& stmt = cursor.GetStatement();

			if ( !Step( stmt ) )
				return {};

			std::optional< std::tuple< T... > > result;
			ReadRowInto( stmt, result );
			return result;
		}

		std::string ExecRaw( std::string_view sql );

		Transaction BeginTransaction( Transaction::Mode mode = Transaction::Mode::Immediate )
		{
			return Transaction( this, mode );
		}

	private:
		void Exec( std::string_view sql );
		Statement Prepare( std::string_view sql );
		bool Step( Statement& stmt );
		void StepOnce( Statement& stmt );

		template < typename Field >
		void ReadOne( Statement& stmt, int index, Field& value )
		{
			using T = std::remove_cvref_t< Field >;

			if constexpr ( detail::is_optional_v< T > )
			{
				using U = typename T::value_type;

				int col_type = sqlite3_column_type( stmt.handle, index );
				if ( col_type == SQLITE_NULL )
				{
					value.reset();
				}
				else
				{
					if ( !value.has_value() )
					{
						value.emplace();
					}
					ReadScalar( stmt.handle, index, *value );
				}
			}
			else
			{
				ReadScalar( stmt.handle, index, value );
			}
		}

		template < typename T >
			requires( !detail::is_std_tuple_v< T > ) and ( DbModel< T > )
		void ReadRowInto( Statement& stmt, std::optional< T >& value )
		{
			if ( not value )
				value.emplace();

			auto& data = value.value();

			int col = 0;
			boost::pfr::for_each_field( data, [ & ]( auto& field ) {
				ReadOne( stmt, col++, field );
			} );
		}

		template < DbModel M >
		void ReadRowIntoAt( Statement& stmt, M& value, int& col )
		{
			boost::pfr::for_each_field( value, [ & ]( auto& field ) {
				ReadOne( stmt, col++, field );
			} );
		}

		template < DbModel... Ts >
		void ReadRowInto( Statement& stmt, std::optional< std::tuple< Ts... > >& value )
		{
			if ( !value )
				value.emplace();

			int col = 0;
			[ & ]< std::size_t... I >( std::index_sequence< I... > ) {
				( ( [ & ] {
					  using M = std::tuple_element_t< I, std::tuple< Ts... > >;
					  auto& opt = std::get< I >( *value );
					  ReadRowIntoAt< M >( stmt, opt, col );
				  }() ),
				  ... );
			}( std::make_index_sequence< sizeof...( Ts ) >{} );
		}

		std::vector< std::string > ReadRowAsString( Statement& stmt );

		template < typename U >
		void ReadScalar( sqlite3_stmt* stmt, int index, U& field )
		{
			using T = std::remove_cvref_t< U >;

			if constexpr ( std::is_same_v< T, bool > )
			{
				field = sqlite3_column_int( stmt, index ) != 0;
			}
			else if constexpr ( std::is_integral_v< T > or std::same_as< ID, T > )
			{
				field = static_cast< T >( sqlite3_column_int64( stmt, index ) );
			}
			else if constexpr ( detail::is_foreign_key_v< T > )
			{
				field.value = static_cast< ID >( sqlite3_column_int64( stmt, index ) );
			}
			else if constexpr ( std::is_enum_v< U > )
			{
				char const* txt = reinterpret_cast< char const* >( sqlite3_column_text( stmt, index ) );
				field = magic_enum::enum_cast< U >( std::string{ txt } ).value();
			}
			else if constexpr ( std::is_floating_point_v< T > )
			{
				field = static_cast< T >( sqlite3_column_double( stmt, index ) );
			}
			else if constexpr ( std::is_same_v< T, std::string > )
			{
				unsigned char const* txt = sqlite3_column_text( stmt, index );
				if ( !txt )
				{
					field.clear();
				}
				else
				{
					int len = sqlite3_column_bytes( stmt, index );
					field.assign( reinterpret_cast< char const* >( txt ), len );
				}
			}
			else if constexpr ( detail::is_time_point_v< U > )
			{
				unsigned char const* txt = sqlite3_column_text( stmt, index );
				if ( !txt )
					throw std::runtime_error( "Time point did not contain a string" );

				std::string_view sv{ reinterpret_cast< char const* >( txt ) };
				field = detail::ParseTimePoint( sv );
			}
			else
			{
				static_assert( false, "Unsupported field type for ReadOne" );
			}
		}

		template < typename U >
		void BindScalar( Statement& stmt, int& index, U const& field )
		{
			using T = std::remove_cvref_t< U >;

			int rc = SQLITE_OK;
			if constexpr ( std::is_same_v< T, ID > )
			{
				if ( field == ID::Zero )
					return;
				rc = sqlite3_bind_int64( stmt.handle, index, static_cast< sqlite3_int64 >( field ) );
			}
			else if constexpr ( detail::is_foreign_key_v< T > )
			{
				rc = sqlite3_bind_int64( stmt.handle, index, static_cast< sqlite3_int64 >( field.value ) );
			}
			else if constexpr ( std::is_same_v< T, bool > || std::is_integral_v< T > )
			{
				rc = sqlite3_bind_int64( stmt.handle, index, static_cast< sqlite3_int64 >( field ) );
			}
			else if constexpr ( std::is_enum_v< U > )
			{
				auto enum_str = magic_enum::enum_name( field );
				rc = sqlite3_bind_text64(
					stmt.handle,
					index,
					enum_str.data(),
					static_cast< sqlite3_uint64 >( enum_str.size() ),
					SQLITE_TRANSIENT,
					SQLITE_UTF8 );
			}
			else if constexpr ( std::is_floating_point_v< T > )
			{
				rc = sqlite3_bind_double( stmt.handle, index, static_cast< double >( field ) );
			}
			else if constexpr ( std::is_same_v< T, std::string > )
			{
				rc = sqlite3_bind_text64(
					stmt.handle,
					index,
					field.c_str(),
					static_cast< sqlite3_uint64 >( field.size() ),
					SQLITE_TRANSIENT,
					SQLITE_UTF8 );
			}
			else if constexpr ( std::is_same_v< T, std::string_view > )
			{
				rc = sqlite3_bind_text64(
					stmt.handle,
					index,
					field.data(),
					static_cast< sqlite3_uint64 >( field.size() ),
					SQLITE_TRANSIENT,
					SQLITE_UTF8 );
			}
			else if constexpr ( detail::is_time_point_v< U > )
			{
				auto tp_str = std::format( "{0:%F}T{0:%T%z}", field );
				rc = sqlite3_bind_text64(
					stmt.handle,
					index,
					tp_str.c_str(),
					static_cast< sqlite3_uint64 >( tp_str.size() ),
					SQLITE_TRANSIENT,
					SQLITE_UTF8 );
			}
			else
			{
				static_assert( false, "Unsupported field type for BindScalar" );
			}

			if ( rc != SQLITE_OK )
			{
				throw SqliteError( sqlite3_errmsg( db_ ) );
			}
			index++;
		}

		template < typename Field >
		void BindOne( Statement& stmt, int& index, Field const& value )
		{
			using T = std::remove_cvref_t< Field >;

			if constexpr ( detail::is_optional_v< T > )
			{
				if ( !value.has_value() )
				{
					int rc = sqlite3_bind_null( stmt.handle, index++ );
					if ( rc != SQLITE_OK )
					{
						throw SqliteError( sqlite3_errmsg( db_ ) );
					}
				}
				else
				{
					BindScalar( stmt, index, *value );
				}
			}
			else
			{
				BindScalar( stmt, index, value );
			}
		}

		char const* ToSqlOp( Cmp op );

		void BindSqlValue( Statement& stmt, int index, SqlValue const& v );

		std::string FormatTable( Statement& stmt, std::vector< std::vector< std::string > > const& rows );

	private:
		sqlite3* db_ = nullptr;
	};

} // namespace iter8::db

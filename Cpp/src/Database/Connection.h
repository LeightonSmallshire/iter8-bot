#pragma once

#include "Model.h"
#include "Query.h"

#include <sqlite3.h>

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

	class Connection
	{
	public:
		Connection( std::string_view path )
		{
			int const flags =
				SQLITE_OPEN_READWRITE |
				SQLITE_OPEN_CREATE |
				SQLITE_OPEN_URI;

			int rc = sqlite3_open_v2( path.data(), &db_, flags, nullptr );
			if ( rc != SQLITE_OK )
			{
				std::string msg = db_ ? sqlite3_errmsg( db_ ) : "failed to open sqlite Connection";
				if ( db_ )
				{
					sqlite3_close_v2( db_ );
					db_ = nullptr;
				}
				throw SqliteError( msg );
			}
		}

		~Connection()
		{
			if ( db_ )
			{
				sqlite3_close_v2( db_ );
				db_ = nullptr;
			}
		}

		Connection( Connection&& other ) noexcept
			: db_( other.db_ )
		{
			other.db_ = nullptr;
		}

		Connection& operator=( Connection&& other ) noexcept
		{
			if ( this != &other )
			{
				if ( db_ )
				{
					sqlite3_close_v2( db_ );
				}
				db_ = other.db_;
				other.db_ = nullptr;
			}
			return *this;
		}

	public:
		struct Statement
		{
			sqlite3_stmt* handle{ nullptr };

			Statement() = default;
			explicit Statement( sqlite3_stmt* stmt )
				: handle( stmt )
			{}

			Statement( Statement const& ) = delete;
			Statement& operator=( Statement const& ) = delete;

			Statement( Statement&& other ) noexcept
				: handle( other.handle )
			{
				other.handle = nullptr;
			}
			Statement& operator=( Statement&& other ) noexcept
			{
				if ( this != &other )
				{
					finalize();
					handle = other.handle;
					other.handle = nullptr;
				}
				return *this;
			}

			~Statement()
			{
				finalize();
			}

			void finalize()
			{
				if ( handle )
				{
					sqlite3_finalize( handle );
					handle = nullptr;
				}
			}

			explicit operator bool() const noexcept
			{
				return handle != nullptr;
			}
		};

		template < DbModel T >
		class DbCursor
		{
		public:
			struct iterator
			{
				using iterator_category = std::input_iterator_tag;
				using value_type = T;
				using difference_type = std::ptrdiff_t;

				Connection* db{ nullptr };
				Statement& stmt{};
				std::optional< T > current{};
				bool started{};

				iterator() = default;
				explicit iterator( Connection* ctx, Statement& statement )
					: db( ctx ), stmt( statement )
				{}

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

				friend bool operator==( iterator const& it,
										std::default_sentinel_t ) noexcept
				{
					return !it.state || it.done_;
				}

				friend bool operator!=( iterator const& it,
										std::default_sentinel_t s ) noexcept
				{
					return !( it == s );
				}

			private:
				void advance()
				{
					if ( started and not current )
						return;

					started = true;

					// Step once
					if ( db->Step( stmt ) )
					{
						db->ReadRowInto( stmt, current );
					}
					else
					{
						current = {};
					}
				}
			};

			explicit DbCursor( Connection* db, Statement stmt )
				: db_{ db }, statement_{ stmt }
			{}

			iterator begin()
			{
				return iterator{ db_, statement_ };
			}

			std::default_sentinel_t end() const noexcept
			{
				return {};
			}

		private:
			Connection* db_;
			Statement statement_;
		};

	public:
		template < typename T >
		void Init()
		{
			auto sql = BuildCreateTableSql< T >();
			Exec( sql );
		}

		template < typename T >
		DbCursor< T > Select( WhereClause< T > const& where = {}, OrderByClause< T > const& order_by = {} )
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
						<< ( o.dir == OrderDir::Desc ? " DESC" : " ASC" );
				}
			}

			oss << ';';

			Statement stmt = Prepare( oss.str() );

			int param_index = 1;
			for ( auto const& w : where )
			{
				BindSqlValue( stmt, param_index++, w.value );
			}

			return DbCursor< T >{ this, std::move( stmt ) };
		}

		template < typename T >
		void Update( T const& data, WhereClause< T > const& where = {} )
		{
			using Traits = DbModelTraits< T >;
			constexpr auto& names = Traits::ColumnNames;
			static_assert( !names.empty(), "DbModelTraits::ColumnNames must not be empty" );

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

			Statement stmt = Prepare( oss.str() );

			// Bind all fields from 'data' first.
			int param_index = 1;
			boost::pfr::for_each_field( data, [ & ]( auto const& field ) {
				BindOne( stmt, param_index++, field );
			} );

			// Then WHERE values.
			for ( auto const& w : where )
			{
				BindSqlValue( stmt, param_index++, w.value );
			}

			StepOnce( stmt );
		}

		template < typename T >
		void Delete( WhereClause< T > const& where = {} )
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

			Statement stmt = Prepare( oss.str() );

			int param_index = 1;
			for ( auto const& w : where )
			{
				BindSqlValue( stmt, param_index++, w.value );
			}

			StepOnce( stmt );
		}


		template < typename T, std::ranges::input_range range_t >
			requires std::same_as< std::ranges::range_value_t< range_t >, T const& >
		void Insert( range_t&& data )
		{
			using Traits = DbModelTraits< T >;
			constexpr auto& names = Traits::ColumnNames;

			std::ostringstream oss;
			oss << "INSERT INTO " << Traits::TableName << " (";

			for ( std::size_t i = 0; i < names.size(); ++i )
			{
				if ( i > 0 )
					oss << ", ";
				oss << detail::ToSnakeCase( names[ i ] );
			}

			oss << ") VALUES (";

			for ( std::size_t i = 0; i < names.size(); ++i )
			{
				if ( i > 0 )
					oss << ", ";
				oss << '?';
			}

			oss << ");";

			Statement stmt = Prepare( oss.str() );

			for ( auto&& elem : data )
			{
				int param_index = 1;
				boost::pfr::for_each_field( elem, [ & ]( auto const& field ) {
					BindOne( stmt, param_index++, field );
				} );

				StepOnce( stmt );
			}
		}

	private:
		void Exec( std::string_view sql )
		{
			char* err = nullptr;
			int rc = sqlite3_exec( db_, sql.data(), nullptr, nullptr, &err );
			if ( rc != SQLITE_OK )
			{
				std::string msg = err ? err : "sqlite exec error";
				if ( err )
				{
					sqlite3_free( err );
				}
				throw SqliteError( msg );
			}
		}

		Statement Prepare( std::string const& sql )
		{
			sqlite3_stmt* stmt = nullptr;

			int rc = sqlite3_prepare_v3(
				db_,
				sql.c_str(),
				-1,
				SQLITE_PREPARE_PERSISTENT,
				&stmt,
				nullptr );

			if ( rc != SQLITE_OK )
			{
				throw std::runtime_error(
					"sqlite3_prepare_v3 failed: " + std::string( sqlite3_errmsg( db_ ) ) );
			}
			return Statement{ stmt };
		}

		bool Step( Statement& stmt )
		{
			if ( !stmt.handle )
				throw std::runtime_error( "Step called on null statement" );

			int rc = sqlite3_step( stmt.handle );
			switch ( rc )
			{
				case SQLITE_ROW:
					return true;
				case SQLITE_DONE:
					return false;
				default:
					throw std::runtime_error( std::format( "sqlite3_step failed: {}", sqlite3_errmsg( db_ ) ) );
			}
		}

		void StepOnce( Statement& stmt )
		{
			if ( !stmt.handle )
				throw std::runtime_error( "StepOnce called on null statement" );

			int rc = sqlite3_step( stmt.handle );
			if ( rc != SQLITE_DONE && rc != SQLITE_ROW )
			{
				throw std::runtime_error( "sqlite3_step (StepOnce) failed: " +
										  std::string( sqlite3_errmsg( db_ ) ) );
			}
			sqlite3_reset( stmt.handle );
			sqlite3_clear_bindings( stmt.handle );
		}

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

		template < DbModel T >
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

		template < typename U >
		void ReadScalar( sqlite3_stmt* stmt, int index, U& field )
		{
			using T = std::remove_cvref_t< U >;

			if constexpr ( std::is_same_v< T, bool > )
			{
				field = sqlite3_column_int( stmt, index ) != 0;
			}
			else if constexpr ( std::is_integral_v< T > )
			{
				field = static_cast< T >( sqlite3_column_int64( stmt, index ) );
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
			else
			{
				static_assert( false, "Unsupported field type for ReadOne" );
			}
		}

		template < typename U >
		void BindScalar( Statement& stmt, int index, U const& field )
		{
			using T = std::remove_cvref_t< U >;

			int rc = SQLITE_OK;
			if constexpr ( std::is_same_v< T, bool > || std::is_integral_v< T > )
			{
				rc = sqlite3_bind_int64( stmt.handle, index, static_cast< sqlite3_int64 >( field ) );
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
			else
			{
				static_assert( false, "Unsupported field type for BindScalar" );
			}

			if ( rc != SQLITE_OK )
			{
				throw SqliteError( sqlite3_errmsg( db_ ) );
			}
		}

		template < typename Field >
		void BindOne( Statement& stmt, int index, Field const& value )
		{
			using T = std::remove_cvref_t< Field >;

			if constexpr ( detail::is_optional_v< T > )
			{
				if ( !value.has_value() )
				{
					int rc = sqlite3_bind_null( stmt.handle, index );
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

		inline char const* ToSqlOp( CmpOp op )
		{
			switch ( op )
			{
				case CmpOp::Eq:
					return "=";
				case CmpOp::Is:
					return "IS";
				case CmpOp::IsNot:
					return "IS NOT";
				case CmpOp::Lt:
					return "<";
				case CmpOp::Le:
					return "<=";
				case CmpOp::Gt:
					return ">";
				case CmpOp::Ge:
					return ">=";
			}
			return "=";
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
			else if constexpr ( std::is_integral_v< T > )
			{
				return SqlValue{ static_cast< std::int64_t >( field ) };
			}
			else if constexpr ( std::is_floating_point_v< T > )
			{
				return SqlValue{ static_cast< double >( field ) };
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

		void BindSqlValue( Statement& stmt, int index, SqlValue const& v )
		{
			int rc = SQLITE_OK;

			if ( std::holds_alternative< std::monostate >( v ) )
			{
				rc = sqlite3_bind_null( stmt.handle, index );
			}
			else if ( auto b = std::get_if< bool >( &v ) )
			{
				rc = sqlite3_bind_int( stmt.handle, index, *b ? 1 : 0 );
			}
			else if ( auto i = std::get_if< std::int64_t >( &v ) )
			{
				rc = sqlite3_bind_int64( stmt.handle, index, *i );
			}
			else if ( auto d = std::get_if< double >( &v ) )
			{
				rc = sqlite3_bind_double( stmt.handle, index, *d );
			}
			else if ( auto s = std::get_if< std::string >( &v ) )
			{
				rc = sqlite3_bind_text64(
					stmt.handle,
					index,
					s->c_str(),
					static_cast< sqlite3_uint64 >( s->size() ),
					SQLITE_TRANSIENT,
					SQLITE_UTF8 );
			}

			if ( rc != SQLITE_OK )
			{
				throw SqliteError( sqlite3_errmsg( db_ ) );
			}
		}

	private:
		sqlite3* db_ = nullptr;
	};

} // namespace iter8::db

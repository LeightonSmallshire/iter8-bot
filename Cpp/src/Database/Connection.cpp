#include "Connection.h"
#include "Connection.h"
#include "Connection.h"

namespace iter8::db
{
	Connection::Connection( std::string_view path )
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

	Connection::~Connection()
	{
		if ( db_ )
		{
			sqlite3_close_v2( db_ );
			db_ = nullptr;
		}
	}

	Connection::Connection( Connection&& other ) noexcept
		: db_( other.db_ )
	{
		other.db_ = nullptr;
	}

	Connection& Connection::operator=( Connection&& other ) noexcept
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

	std::string Connection::ExecRaw( std::string_view sql )
	{
		std::vector< std::vector< std::string > > result;

		Statement stmt = Prepare( sql );

		int row_count = 0;
		while ( Step( stmt ) )
		{
			result.push_back( ReadRowAsString( stmt ) );
		}

		if ( result.empty() )
			return {};

		return FormatTable( stmt, result );
	}

	void Connection::Exec( std::string_view sql )
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

	Statement Connection::Prepare( std::string_view sql )
	{
		sqlite3_stmt* stmt = nullptr;

		int rc = sqlite3_prepare_v3(
			db_,
			sql.data(),
			-1,
			SQLITE_PREPARE_PERSISTENT,
			&stmt,
			nullptr );

		if ( rc != SQLITE_OK )
		{
			auto err = "sqlite3_prepare_v3 failed: " + std::string( sqlite3_errmsg( db_ ) );
			throw std::runtime_error( err );
		}
		return Statement{ stmt };
	}

	bool Connection::Step( Statement& stmt )
	{
		if ( !stmt.handle )
			throw std::runtime_error( "Step called on null Connection::Statement" );

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

	void Connection::StepOnce( Statement& stmt )
	{
		if ( !stmt.handle )
			throw std::runtime_error( "StepOnce called on null Connection::Statement" );

		int rc = sqlite3_step( stmt.handle );
		if ( rc != SQLITE_DONE && rc != SQLITE_ROW )
		{
			throw std::runtime_error( "sqlite3_step (StepOnce) failed: " +
									  std::string( sqlite3_errmsg( db_ ) ) );
		}
		sqlite3_reset( stmt.handle );
		sqlite3_clear_bindings( stmt.handle );
	}

	std::vector< std::string > Connection::ReadRowAsString( Statement& stmt )
	{
		std::vector< std::string > row;

		int n = sqlite3_column_count( stmt.handle );

		for ( int i = 0; i < n; i++ )
		{
			unsigned char const* txt = sqlite3_column_text( stmt.handle, i );
			if ( txt )
			{
				row.emplace_back( reinterpret_cast< char const* >( txt ) );
			}
			else
			{
				void const* data = sqlite3_column_blob( stmt.handle, i );
				if ( data )
				{
					int size = sqlite3_column_bytes( stmt.handle, i );
					auto str = std::string_view{ reinterpret_cast< char const* >( data ), static_cast< std::size_t >( size ) };
					row.emplace_back( str );
				}
				else
				{
					row.emplace_back( "NULL" );
				}
			}
		}

		return row;
	}

	char const* Connection::ToSqlOp( Cmp op )
	{
		switch ( op )
		{
			case Cmp::Eq:
				return "=";
			case Cmp::Is:
				return "IS";
			case Cmp::IsNot:
				return "IS NOT";
			case Cmp::Lt:
				return "<";
			case Cmp::Le:
				return "<=";
			case Cmp::Gt:
				return ">";
			case Cmp::Ge:
				return ">=";
		}
		return "=";
	}

	void Connection::BindSqlValue( Statement& stmt, int index, SqlValue const& v )
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

	std::string Connection::FormatTable( Statement& stmt, std::vector< std::vector< std::string > > const& rows )
	{
		auto headings = std::vector< std::string >{};

		int n = sqlite3_column_count( stmt.handle );
		for ( int i = 0; i < n; ++i )
		{
			char const* name = sqlite3_column_name( stmt.handle, i );
			headings.emplace_back( name );
		}

		std::vector< std::size_t > widths( n, 0 );
		for ( auto const& row : rows )
		{
			for ( std::size_t c = 0; c < row.size(); ++c )
			{
				widths[ c ] = Max( widths[ c ], headings[ c ].size(), row[ c ].size() );
			}
		}

		std::ostringstream out;

		for ( std::size_t c = 0; c < n; ++c )
		{
			auto const& heading = headings[ c ];
			out << headings[ c ];

			if ( heading.size() < widths[ c ] )
			{
				out << std::string( widths[ c ] - heading.size(), ' ' );
			}

			if ( c + 1 < n )
			{
				out << " | ";
			}
		}

		out << '\n';

		for ( std::size_t c = 0; c < n; ++c )
		{
			auto extra = c == 0 ? 1 : 2;
			out << std::string( widths[ c ] + extra, '-' );
			if ( c + 1 < n )
				out << '+';
		}

		out << '\n';

		for ( auto const& row : rows )
		{
			for ( std::size_t c = 0; c < n; ++c )
			{
				auto const& value = row[ c ];
				out << value;

				if ( value.size() < widths[ c ] )
				{
					out << std::string( widths[ c ] - value.size(), ' ' );
				}

				if ( c + 1 < n )
				{
					out << " | ";
				}
			}
			out << '\n';
		}

		return out.str();
	}
} // namespace iter8::db
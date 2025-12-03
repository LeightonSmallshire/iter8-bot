#include "Files.h"

#include "Logging/Log.h"

#include <archive.h>
#include <archive_entry.h>

namespace iter8
{
	namespace fs = std::filesystem;

	namespace
	{
		static void CheckArchive( int r, archive* a, char const* what )
		{
			if ( r < ARCHIVE_OK )
			{
				auto const* msg = archive_error_string( a );
				int err_no = archive_errno( a );
				throw std::runtime_error(
					std::string( what ) +
					" failed, code=" + std::to_string( r ) +
					", errno=" + std::to_string( err_no ) +
					", msg=" + ( msg ? msg : "(no message)" ) );
			}

			if ( r > ARCHIVE_OK )
			{
				auto const* msg = archive_error_string( a );
				log::Error( "{} warning, code={}, msg={}", what, r, ( msg ? msg : "(no message)" ) );
			}
		}

		static void AddPathToZip( archive* a,
								  fs::path const& root,
								  fs::path const& p )
		{
			fs::path rel = fs::relative( p, root );
			std::string rel_str = rel.generic_string();

			bool const is_dir = fs::is_directory( p );
			bool const is_regular = fs::is_regular_file( p );

			if ( !is_dir && !is_regular )
			{
				// skip symlinks, sockets, etc.
				return;
			}

			archive_entry* entry = archive_entry_new();

			if ( is_dir )
			{
				if ( rel_str.empty() )
				{
					// For the root dir itself, choose a nice name, e.g. "<rootname>/"
					rel_str = root.filename().generic_string();
				}

				// ZIP: directory names should end with '/'
				if ( !rel_str.empty() && rel_str.back() != '/' )
					rel_str.push_back( '/' );

				archive_entry_set_pathname( entry, rel_str.c_str() );
				archive_entry_set_filetype( entry, AE_IFDIR );
				archive_entry_set_perm( entry, 0755 );
				archive_entry_set_size( entry, 0 );

				// Helpful: log the path you’re adding
				log::Info( "Adding dir {}", rel_str );

				CheckArchive( archive_write_header( a, entry ), a, "archive_write_header(dir)" );

				archive_entry_free( entry );
				return;
			}

			// Regular file
			auto const filesize = fs::file_size( p );

			if ( rel_str.empty() )
				rel_str = p.filename().generic_string();

			archive_entry_set_pathname( entry, rel_str.c_str() );
			archive_entry_set_filetype( entry, AE_IFREG );
			archive_entry_set_perm( entry, 0644 );
			archive_entry_set_size( entry, static_cast< la_int64_t >( filesize ) );

			log::Info( "Adding file {} ({} bytes)", rel_str, filesize );

			CheckArchive( archive_write_header( a, entry ), a, "archive_write_header(file)" );

			std::ifstream in( p, std::ios::binary );
			if ( !in )
			{
				archive_entry_free( entry );
				throw std::runtime_error( "Failed to open file: " + p.string() );
			}

			char buffer[ 64 * 1024 ];
			while ( in )
			{
				in.read( buffer, sizeof( buffer ) );
				std::streamsize const n = in.gcount();
				if ( n > 0 )
				{
					la_ssize_t const written =
						archive_write_data( a, buffer, static_cast< size_t >( n ) );
					if ( written < 0 )
					{
						auto const* msg = archive_error_string( a );
						archive_entry_free( entry );
						throw std::runtime_error(
							msg ? msg : "archive_write_data failed" );
					}
				}
			}

			CheckArchive( archive_write_finish_entry( a ), a, "archive_write_finish_entry" );

			archive_entry_free( entry );
		}
	}

	std::vector< char > ReadFileBinary( std::filesystem::path const& path )
	{
		std::ifstream file( path, std::ios::binary | std::ios::ate );
		if ( !file )
		{
			throw std::runtime_error( "Failed to open file: " + path.string() );
		}

		auto const size = static_cast< std::size_t >( file.tellg() );
		file.seekg( 0, std::ios::beg );

		std::vector< char > buffer( size );
		if ( !file.read( buffer.data(), static_cast< std::streamsize >( size ) ) )
		{
			throw std::runtime_error( "Failed to read file: " + path.string() );
		}

		return buffer;
	}

	fs::path CompressDirectory( std::filesystem::path const& dir )
	{
		std::string out_path =
			( std::filesystem::temp_directory_path() / ( dir.filename().string() + ".zip" ) ).string();

		if ( !fs::exists( dir ) || !fs::is_directory( dir ) )
		{
			throw std::runtime_error(
				"Input path is not a directory: " + dir.string() );
		}

		archive* a = archive_write_new();
		if ( !a )
			throw std::runtime_error( "archive_write_new failed" );

		CheckArchive( archive_write_set_format_zip( a ),
					  a,
					  "archive_write_set_format_zip" );

		CheckArchive( archive_write_open_filename( a, out_path.c_str() ),
					  a,
					  "archive_write_open_filename" );

		// Root directory entry: root == dir
		AddPathToZip( a, dir, dir );

		for ( auto const& entry : fs::recursive_directory_iterator( dir ) )
		{
			AddPathToZip( a, dir, entry.path() );
		}

		CheckArchive( archive_write_close( a ), a, "archive_write_close" );
		archive_write_free( a );

		return out_path;
	}
} // namespace iter8
#include "DevCog.h"

#include "Core/Files.h"
#include "Model/Log.h"
#include "Logging/Log.h"

namespace iter8
{
	DevCog::DevCog( Context& ctx )
		: Cog( ctx )
	{
		auto level_param = CommandArgumentDefinition{
			.type = dpp::co_string,
			.name = "level",
			.required = false,
		};
		auto limit_param = CommandArgumentDefinition{
			.type = dpp::co_integer,
			.name = "limit",
			.required = false,
		};

		AddCommand( { "logs", "Get the bot logs", { level_param, limit_param } }, std::bind_front( &DevCog::OnGetLogs, this ) );

		auto path_parm = CommandArgumentDefinition{
			.type = dpp::co_string,
			.name = "path",
			.required = true,
			.autocomplete = std::bind_front( &DevCog::OnDownloadAutocomplete, this ),
		};
		AddCommand( { "download", "Download files", { path_parm } }, std::bind_front( &DevCog::OnDownload, this ) );

		AddCommand( { "crash", "KABOOM!" }, std::bind_front( &DevCog::OnCrash, this ) );
	}

	dpp::task< void > DevCog::OnGetLogs( dpp::slashcommand_t const& event )
	{
		if ( not Users::IsTrusted( event.command.usr.id ) )
		{
			co_await event.co_reply( "No logs 4 U" );
			co_return;
		}

		co_await event.co_thinking( true );

		auto target = GetParameter< std::string >( event, "level" ).and_then( []( auto l ) { return magic_enum::enum_cast< spdlog::level::level_enum >( l ); } );
		auto limit = GetParameter< std::int64_t >( event, "limit" ).value_or( 100 );

		auto where = target.has_value() ? db::Where< Log >( db::WhereParam{ &Log::level, *target } ) : db::WhereClause< Log >{};
		auto order = db::OrderBy< Log >( db::OrderParam{ &Log::id, db::Ordering::Desc } );

		auto result = ctx_.db.Select< Log >( where, order );
		auto logs = result | std::views::take( limit ) | std::ranges::to< std::vector >() | std::views::reverse;

		if ( logs.empty() )
		{
			co_await event.co_follow_up( "No logs found" );
			co_return;
		}

		std::ostringstream oss;
		oss << "```\n";

		for ( auto const& log : logs )
		{
			oss << std::format( "[{0:%F}T{0:%T%z}] [{1}] {2}\n", log.timestamp, log.level, log.message );
		}

		oss << "```";

		co_await event.co_follow_up( oss.str() );
	}

	dpp::task< void > DevCog::OnDownload( dpp::slashcommand_t const& event )
	{
		if ( not Users::IsTrusted( event.command.usr.id ) )
		{
			co_await event.co_reply( "No files 4 U" );
			co_return;
		}

		co_await event.co_thinking( true );

		std::filesystem::path path = GetParameter< std::string >( event, "path" ).value();

		if ( std::filesystem::is_directory( path ) )
		{
			auto zip_path = CompressDirectory( path );
			auto zip_data = ReadFileBinary( zip_path );
			std::filesystem::remove( zip_path );

			auto msg = dpp::message{};
			msg.add_file( zip_path.filename().string(), std::string_view{ zip_data.data(), zip_data.size() } );

			co_await event.co_follow_up( msg );
		}
		else if ( std::filesystem::is_regular_file( path ) )
		{
			auto data = ReadFileBinary( path );

			auto msg = dpp::message{};
			msg.add_file( path.filename().string(), std::string_view{ data.data(), data.size() } );

			co_await event.co_follow_up( msg );
		}
		else
		{
			co_await event.co_follow_up( "Not a valid file!" );
		}
	}

	dpp::task< void > DevCog::OnCrash( dpp::slashcommand_t const& event )
	{
		if ( not Users::IsTrusted( event.command.usr.id ) )
		{
			co_await event.co_reply( std::format( "Stop it {}", event.command.usr.get_mention() ) );
			co_return;
		}

		auto gif = dpp::embed{};
		gif.set_title( "Bye bye..." );
		gif.set_image( "https://c.tenor.com/gkrf_4O0tVMAAAAd/tenor.gif" );

		auto reply = dpp::message{};
		reply.add_embed( gif );
		reply.set_flags( dpp::m_ephemeral );

		co_await event.co_reply( reply );
		std::exit( 0 );

		auto failed = dpp::message{ event.command.channel_id, "Crash failed." };
		co_await ctx_.bot.co_message_create( failed );
	}

	namespace
	{
		namespace fs = std::filesystem;
		static std::string ExpandPath( std::string_view input )
		{
			std::string s( input );

			// Expand leading '~' -> $HOME or %USERPROFILE%
			if ( !s.empty() && s[ 0 ] == '~' )
			{
				char const* home =
#ifdef _WIN32
					std::getenv( "USERPROFILE" );
#else
					std::getenv( "HOME" );
#endif
				if ( home )
				{
					s.erase( 0, 1 );
					s.insert( 0, home );
				}
			}

			// Very simple "$VAR/..." expansion at the start
			if ( !s.empty() && s[ 0 ] == '$' )
			{
				std::size_t pos = 1;
				while ( pos < s.size() &&
						( std::isalnum( static_cast< unsigned char >( s[ pos ] ) ) || s[ pos ] == '_' ) )
				{
					++pos;
				}
				std::string var_name = s.substr( 1, pos - 1 );
				if ( char const* val = std::getenv( var_name.c_str() ) )
				{
					std::string rest = s.substr( pos );
					s = std::string( val ) + rest;
				}
			}

			return s;
		}

		static std::vector< dpp::command_option_choice > AutocompletePath( std::string const& current_raw )
		{
			std::string current = ExpandPath( current_raw );
			std::vector< std::string > matches;

			fs::path p( current );

			try
			{
				if ( fs::is_directory( p ) )
				{
					// Equivalent of glob(current + "/*")
					for ( auto const& entry : fs::directory_iterator( p ) )
					{
						std::string path_str = fs::relative( entry.path() ).string();
						if ( entry.is_directory() )
						{
							path_str += '/';
						}
						matches.push_back( std::move( path_str ) );
					}
				}
				else
				{
					// Equivalent of f"{current}*"
					fs::path parent = p.parent_path();
					std::string prefix = p.filename().string();
					if ( parent.empty() )
					{
						parent = fs::current_path();
					}

					if ( fs::exists( parent ) && fs::is_directory( parent ) )
					{
						for ( auto const& entry : fs::directory_iterator( parent ) )
						{
							std::string name = entry.path().filename().string();
							if ( name.starts_with( prefix ) )
							{
								std::string path_str = fs::relative( entry.path() ).string();
								if ( entry.is_directory() )
								{
									path_str += '/';
								}
								matches.push_back( std::move( path_str ) );
							}
						}
					}
				}
			}
			catch ( fs::filesystem_error const& )
			{
				// Ignore filesystem errors: just return empty suggestions
			}

			std::ranges::sort( matches );
			if ( matches.size() > 25 )
			{
				matches.resize( 25 );
			}

			std::vector< dpp::command_option_choice > choices;
			choices.reserve( matches.size() );
			for ( auto const& s : matches )
			{
				choices.emplace_back( s, s );
			}

			return choices;
		}
	} // namespace

	dpp::task< void > DevCog::OnDownloadAutocomplete( dpp::autocomplete_t const& e, dpp::command_option const& opt )
	{
		auto response = dpp::interaction_response( dpp::ir_autocomplete_reply );
		if (not Users::IsTrusted(e.command.usr.id))
		{
			response.autocomplete_choices = { { "BAD BAD STOP IT", "" } };
			co_await ctx_.bot.co_interaction_response_create( e.command.id, e.command.token, response );
			co_return;
		}

		auto current = std::get< std::string >( opt.value );

		response.autocomplete_choices = AutocompletePath( current );

		co_await ctx_.bot.co_interaction_response_create( e.command.id, e.command.token, response );
	}
} // namespace iter8
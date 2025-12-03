#include "DevCog.h"

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
			.required = false
		};
		auto limit_param = CommandArgumentDefinition{
			.type = dpp::co_integer,
			.name = "limit",
			.required = false
		};

		AddCommand( { "logs", "Get the bot logs", { level_param, limit_param } }, std::bind_front( &DevCog::OnGetLogs, this ) );
	}

	dpp::task< void > DevCog::OnGetLogs( dpp::slashcommand_t const& event )
	{
		if ( not Users::IsTrustedUser( event.command.usr.id ) )
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

		if (logs.empty())
		{
			co_await event.co_follow_up( "No logs found" );
			co_return;
		}

		std::ostringstream oss;
		oss << "```\n";

		for (auto const& log : logs)
		{
			oss << std::format( "[{0:%F}T{0:%T%z}] [{1}] {2}\n", log.timestamp, log.level, log.message );
		}

		oss << "```";

		co_await event.co_follow_up( oss.str() );
	}
} // namespace iter8
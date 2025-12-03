#include "Bot.h"

#include "Cogs/BotBrokenCog.h"
#include "Cogs/DevCog.h"

#include "Model/User.h"
#include "Model/Log.h"

#include "Logging/Log.h"

namespace iter8
{
	DiscordBot::DiscordBot()
		: ctx_{
			.bot{ std::getenv( "DISCORD_TOKEN" ), dpp::i_default_intents | dpp::i_guild_members | dpp::i_message_content | dpp::i_guild_message_reactions },
			.db{ "data/storage.db" }
		}
	{
		ctx_.db.Init< User >();
		ctx_.db.Init< Log >();

		log::Init( ctx_.db );

		RegisterCog< BotBrokenCog >();
		RegisterCog< DevCog >();

		ctx_.bot.on_autocomplete( [ this ]( dpp::autocomplete_t const& e ) -> dpp::task< void > {
			if ( not ctx_.autocomplete_handlers.contains( e.name ) )
				co_return;

			auto const& handlers = ctx_.autocomplete_handlers[ e.name ];
			auto it = std::ranges::find_if( e.options, [ & ]( auto const& o ) {
				return o.focused and handlers.contains( o.name );
			} );

			if ( it == e.options.end() )
				co_return;

			co_await handlers.at( it->name )( e, *it );
		} );

		log::Info( "Bot starting..." );
		ctx_.bot.start( dpp::st_wait );
	}
} // namespace iter8
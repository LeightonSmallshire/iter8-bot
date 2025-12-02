#include "Bot.h"

#include "Cogs/BotBrokenCog.h"

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

		ctx_.bot.start( dpp::st_wait );
	}
} // namespace iter8

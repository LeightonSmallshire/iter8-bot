#include "Bot.h"

#include "Cogs/BotBrokenCog.h"
#include "Model/User.h"

namespace iter8
{
	DiscordBot::DiscordBot()
		: ctx_{
			.bot{ std::getenv( "DISCORD_TOKEN" ), dpp::i_default_intents | dpp::i_guild_members | dpp::i_message_content | dpp::i_guild_message_reactions },
			.db{ "data/storage.db" }
		}
	{
		RegisterCog< BotBrokenCog >();

		ctx_.db.Init< User >();

		ctx_.bot.start( dpp::st_wait );
	}
} // namespace iter8
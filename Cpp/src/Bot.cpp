#include "Bot.h"

#include "Cogs/BotBrokenCog.h"

namespace iter8
{
	DiscordBot::DiscordBot()
		: bot_{ std::getenv( "DISCORD_TOKEN" ), dpp::i_default_intents | dpp::i_guild_members | dpp::i_message_content | dpp::i_guild_message_reactions }
	{
		RegisterCog< BotBrokenCog >();

		bot_.start( dpp::st_wait );
	}
} // namespace iter8
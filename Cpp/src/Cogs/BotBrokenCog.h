#pragma once

#include "Cog.h"

namespace iter8
{
	class BotBrokenCog : public Cog
	{
	public:
		BotBrokenCog( dpp::cluster& bot );

		dpp::task< void > OnBrokenCommand( dpp::slashcommand_t const& event );
		dpp::task< void > OnWorkingCommand( dpp::slashcommand_t const& event );
		dpp::task< void > OnMessage( dpp::message_create_t const& event );
	};
}
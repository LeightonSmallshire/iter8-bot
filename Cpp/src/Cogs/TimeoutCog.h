#pragma once

#include "Cog.h"

namespace iter8
{
	struct TimeoutInfo
	{
		dpp::snowflake moderator;
		std::string reason;
	};

	class TimeoutCog : public Cog
	{
	public:
		TimeoutCog( Context& ctx );

	private:
		dpp::task< void > OnLeaderboardCommand( dpp::slashcommand_t const& event );
		dpp::task< void > OnMemberUpdate( dpp::guild_member_update_t const& event );

		dpp::task< void > OnMemberTimeout( dpp::guild const& guild, dpp::guild_member const& member, TimePoint ts, std::optional< TimeoutInfo > timeout_info );
		dpp::task< void > OnMemberUntimeout( dpp::guild const& guild, dpp::guild_member const& member, std::optional< TimeoutInfo > timeout_info );
	};
}
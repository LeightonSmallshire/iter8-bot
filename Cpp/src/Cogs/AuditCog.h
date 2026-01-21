#pragma once

#include "Cog.h"
#include <mutex>

namespace iter8
{
	class AuditCog : public Cog
	{
		std::mutex updating_mutex_;

	public:
		AuditCog( Context& ctx );

		dpp::task< void > doRefresh(dpp::ready_t const& event);

		// dpp::task< void > OnLeaderboardCommand( dpp::slashcommand_t const& event );
		// dpp::task< void > OnMemberUpdate( dpp::guild_member_update_t const& event );

		// dpp::task< void > OnMemberTimeout( dpp::guild const& guild, dpp::guild_member const& member, TimePoint ts, std::optional< TimeoutInfo > timeout_info );
		// dpp::task< void > OnMemberUntimeout( dpp::guild const& guild, dpp::guild_member const& member, std::optional< TimeoutInfo > timeout_info );
	};
} // namespace iter8

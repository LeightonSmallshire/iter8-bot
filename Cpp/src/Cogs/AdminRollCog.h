#pragma once

#include "Cog.h"

namespace iter8
{
	class AdminRollCog : public Cog
	{
	public:
		AdminRollCog( Context& ctx );

	private:
		dpp::task< void > OnRollAdminCommand( dpp::slashcommand_t const& event );
	};
} // namespace iter8
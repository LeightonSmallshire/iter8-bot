#pragma once

#include "Cog.h"

namespace iter8
{
	class DevCog : public Cog
	{
	public:
		DevCog( Context& ctx ); 

		dpp::task< void > OnGetLogs( dpp::slashcommand_t const& event );
	};
}
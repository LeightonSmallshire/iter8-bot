#pragma once

#include "Cog.h"

namespace iter8
{
	class GiftingCog : public Cog
	{
	public:
		GiftingCog( Context& ctx );

	private:
		dpp::task< void > OnReactionAdded( dpp::message_reaction_add_t const& );
		dpp::task< void > OnReactionRemoved( dpp::message_reaction_remove_t const& );
	};

}
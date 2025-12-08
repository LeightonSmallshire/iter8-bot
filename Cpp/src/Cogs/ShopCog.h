#pragma once

#include "Cog.h"

namespace iter8
{
	class ShopCog : public Cog
	{
	public:
		ShopCog( Context& ctx );

		dpp::task< void > OnShopCommand( dpp::slashcommand_t const& event );
		dpp::task< void > OnCreditCommand( dpp::slashcommand_t const& event );
	};

}
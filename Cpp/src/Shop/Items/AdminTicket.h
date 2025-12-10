#pragma once

#include "Core/Discord.h"
#include "Model/InventoryItem.h"
#include "Shop/Item.h"

namespace iter8::shop
{
	class AdminTicket : public Handler
	{
	public:
		AdminTicket( Context& ctx )
			: Handler( ctx )
		{}

		dpp::task< void > HandlePurchase( dpp::interaction_create_t const& event, std::map< std::string, std::any > const& params ) override
		{
			ctx_.db.Insert< InventoryItem >( InventoryItem{
				.user_id = db::ToId( event.command.usr.id ),
				.item_id = db::ToId( ItemId::AdminTicket ),
			} );
			
			co_return;
		}

		std::vector< InputType > GetInputHandlers()
		{
			return {};
		}
	};
} // namespace iter8::shop
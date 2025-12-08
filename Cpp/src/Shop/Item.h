#pragma once

#include "Database/Model.h"

#include "dpp/dpp.h"

namespace iter8::shop
{
	enum class ItemId : std::uint64_t
	{
		AdminTimeout = 1,
		UserTimeout = 2,
		BullyTimeout = 5,
		RandomTimeout = 14,
		BullyReroll = 3,
		BullyChoose = 4,
		AdminTicket = 7,
		AdminReroll = 8,
		MakeAdmin = 6,
		ChooseNicknameSelf = 9,
		ChooseNicknameOther = 10,
		ChooseColourSelf = 11,
		ChooseColourOther = 12,
		BlackFridaySale = 13
	};

	class ItemHandler
	{
	public:
		virtual ~ItemHandler() = default;
		virtual dpp::task< void > HandlePurchase( dpp::interaction_create_t& event, std::map< std::string, std::any > const& params ) = 0;
		virtual std::vector< dpp::component > GetInputHandlers()
		{
			return {};
		}
	};

	std::shared_ptr< ItemHandler > GetShopHandler( db::ID item_id );
}
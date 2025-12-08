#pragma once

#include "User.h"
#include "ShopItem.h"

#include "Database/Model.h"

namespace iter8
{
	struct InventoryItem
	{
		db::ID id;
		db::ForeignKey< User > user_id;
		db::ForeignKey< ShopItem > item_id;
		bool used;
	};
} // namespace iter8
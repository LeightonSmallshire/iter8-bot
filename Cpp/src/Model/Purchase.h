#pragma once

#include "User.h"
#include "ShopItem.h"

#include "Database/Model.h"

namespace iter8
{
	struct Purchase
	{
		db::ID id;
		db::ForeignKey< User > user_id;
		db::ForeignKey< ShopItem > item_id;
		TimePoint timestamp;
		int cost;
	};
} // namespace iter8
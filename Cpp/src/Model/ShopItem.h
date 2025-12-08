#pragma once

#include "User.h"

#include "Database/Model.h"

namespace iter8
{
	enum class Category
	{
		Timeout,
		Admin,
		Customise,
		Sale
	};

	struct ShopItem
	{
		db::ID id;
		int cost;
		std::string description;
		Category category;
	};
}
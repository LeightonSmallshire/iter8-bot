#pragma once

#include "User.h"

#include "Database/Model.h"

#include "magic_enum/magic_enum.hpp"
#include "nlohmann/json.hpp"

namespace iter8
{
	enum class Category
	{
		Timeout,
		Admin,
		Customise,
		Sale
	};

	inline void from_json( nlohmann::json const& j, Category& e )
	{
		e = magic_enum::enum_cast< Category >( j.get< std::string_view >() ).value();
	}

	struct ShopItem
	{
		db::ID id;
		int cost;
		std::string description;
		Category category;
	};

	inline void from_json( nlohmann::json const& j, ShopItem& si )
	{
		j.at( "id" ).get_to( si.id );
		j.at( "cost" ).get_to( si.cost );
		j.at( "description" ).get_to( si.description );
		j.at( "category" ).get_to( si.category );
	}

	inline std::vector< ShopItem > ReadItemsJson()
	{
		static constexpr auto filename = "data/shop_items.json";
		std::ifstream f( filename );
		nlohmann::json data = nlohmann::json::parse( f );
		return data.get< std::vector< ShopItem > >();
	}
} // namespace iter8
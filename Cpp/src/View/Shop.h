#pragma once

#include "Component.h" 

#include "Shop/Item.h"

namespace iter8::view
{
	class Shop
	{
	public:
		Shop( Context& ctx );

		dpp::component Root()
		{
			return root_;
		}

	private:
		std::map< shop::InputType, dpp::component > MakeInputComponents( Context& ctx );

	private:
		dpp::component root_{};

		struct ShopContext
		{
			std::optional< shop::ItemId > selected{};
			std::map< std::string, std::any > params{};
			std::map< shop::InputType, dpp::component > components{};
		};
		std::shared_ptr< ShopContext > ctx_;
	};
}
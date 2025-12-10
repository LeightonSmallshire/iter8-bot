#pragma once

#include "Components/Component.h" 

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
		std::map< shop::InputType, std::unique_ptr< Component > > MakeInputComponents( Context& ctx );

	private:
		dpp::component root_{};

		struct ShopContext
		{
			std::optional< shop::ItemId > selected{};
			std::map< std::string, std::any > params{};
			std::map< shop::InputType, std::unique_ptr< Component > > components{};
		};
		std::shared_ptr< ShopContext > ctx_;
	};
}
#pragma once

#include "Component.h" 

#include "Shop/Item.h"

namespace iter8::view
{
	class Shop
	{
	public:
		Shop( Context& ctx );

		dpp::message const& Message()
		{
			return ctx_->message;
		}

	private:
		
		std::map< shop::InputType, dpp::component > MakeInputComponents( Context& ctx );

	private:
		struct ShopContext
		{
			dpp::message message{};

			std::optional< shop::ItemId > selected{};
			std::map< std::string, std::any > params{};
			std::map< shop::InputType, dpp::component > components{};
		};
		std::shared_ptr< ShopContext > ctx_;
	};
}
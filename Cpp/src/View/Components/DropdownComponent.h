#pragma once

#include "Component.h"

namespace iter8::view
{
	struct DropdownData : ComponentData
	{
		std::string placeholder;
		std::vector< dpp::select_option > options;
	};

	class Dropdown : public Component
	{
	public:
		Dropdown( Context& ctx, DropdownData const& init_data )
			: Component( ctx, init_data )
		{
			component_.set_type( dpp::cot_selectmenu )
				.set_placeholder( init_data.placeholder )
				.set_min_values( 1 )
				.set_max_values( 1 );

			component_.options = init_data.options;
		}
	};
} // namespace iter8::view
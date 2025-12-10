#pragma once

#include "Component.h"

namespace iter8::view
{
	struct UserSelectData : ComponentData
	{
		std::string placeholder;
	};

	class UserSelect : public Component
	{
	public:
		UserSelect( Context& ctx, UserSelectData const& init_data )
			: Component( ctx, init_data )
		{
			component_.set_type( dpp::cot_user_selectmenu )
				.set_placeholder( init_data.placeholder	)
				.set_min_values( 1 )
				.set_max_values( 1 );
		}
	};
} // namespace iter8::view
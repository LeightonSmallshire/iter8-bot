#pragma once

#include "Component.h"

namespace iter8::view
{
	struct ButtonData : ComponentData
	{};

	class Button : public Component
	{
	public:
		Button( Context& ctx, ButtonData const& init_data )
			: Component( ctx, init_data )
		{
			component_.set_type( dpp::cot_button );
		}
	};
} // namespace iter8::view
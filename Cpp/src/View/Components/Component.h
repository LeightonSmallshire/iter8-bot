#pragma once

#include "Context.h"

#include "dpp/dpp.h"

namespace iter8::view
{
	struct ComponentData
	{
		std::string id;
		std::string label;
		std::string emoji;
		dpp::component_style style;
		ComponentHandler handler;
	};

	class Component
	{
	public:
		Component( Context& ctx, ComponentData const& init_data )
			: ctx_( ctx )
		{
			component_.set_label( init_data.label )
				.set_emoji( init_data.emoji )
				.set_style( init_data.style )
				.set_id( init_data.id );

			ctx_.component_handlers[ init_data.id ] = std::move( init_data.handler );
		}

		virtual ~Component() = default;

		dpp::component Root() const
		{
			dpp::component root{};
			root.add_component( component_ );
			return root;
		}

	protected:
		Context& ctx_;
		dpp::component component_{};
	};
} // namespace iter8::view
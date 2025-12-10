#pragma once

#include "Context.h"

#include "dpp/dpp.h"

namespace iter8::view
{
	struct ComponentData
	{
		dpp::component_type type;
		std::string id;
		std::string label;
		std::string emoji;
		std::string placeholder;
		dpp::component_style style;
		dpp::text_style_type text_style;
		std::int32_t min_length;
		std::int32_t max_length;
		std::vector< dpp::select_option > options;
		ComponentHandler handler;
	};

	struct ModalData
	{
		std::string id;
		std::string title;
		std::vector< dpp::component > components{};
		ComponentHandler handler;
	};

	inline dpp::component MakeComponent( Context& ctx, ComponentData const& init_data )
	{
		auto component = dpp::component{}
							 .set_id( init_data.id )
							 .set_label( init_data.label )
							 .set_emoji( init_data.emoji )
							 .set_style( init_data.style )
							 .set_placeholder( init_data.placeholder )
							 .set_text_style( init_data.text_style )
							 .set_min_length( init_data.min_length )
							 .set_max_length( init_data.max_length )
							 .set_type( init_data.type );

		for ( auto const& opt : init_data.options )
			component.add_select_option( opt );

		if ( init_data.handler )
			ctx.component_handlers[ init_data.id ] = init_data.handler;

		return component;
	}

	inline dpp::interaction_modal_response MakeModal( Context& ctx, ModalData const& init_data )
	{
		dpp::interaction_modal_response modal( init_data.id, init_data.title );

		for ( auto const& comp : init_data.components )
			modal.add_component( comp );

		if ( init_data.handler )
			ctx.component_handlers[ init_data.id ] = init_data.handler;

		return modal;
	}
} // namespace iter8::view
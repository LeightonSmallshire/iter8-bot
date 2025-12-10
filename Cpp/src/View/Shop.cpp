#include "Shop.h"

#include "Model/ShopItem.h"

#include "Components/DropdownComponent.h"
#include "Components/ButtonComponent.h"
#include "Components/UserSelectComponent.h"

namespace iter8::view
{
	Shop::Shop( Context& bot_ctx )
		: ctx_{ std::make_shared< ShopContext >() }
	{
		ctx_->components = MakeInputComponents( bot_ctx );

		auto select_options = std::vector< dpp::select_option >{};

		auto items = bot_ctx.db.Select< ShopItem >().ReadAll();
		std::ranges::sort( items, std::less{}, []( auto const& i ) { return std::to_underlying( i.category ); } );
		auto groups = items | std::views::chunk_by( []( auto const& a, auto const& b ) { return a.category == b.category; } ) | std::ranges::to< std::vector >();

		for ( auto&& group : groups )
		{
			for ( auto const& item : group )
			{
				auto& option = select_options.emplace_back();
				option.label = magic_enum::enum_name( static_cast< shop::ItemId >( std::to_underlying( item.id ) ) );
				option.description = item.description;
				option.value = option.label;
			}
		}

		DropdownData options_cd{};
		options_cd.id = std::format( "{}-shop-select", ( uintptr_t )this );
		options_cd.placeholder = "Choose an item...";
		options_cd.options = std::move( select_options );
		options_cd.handler = [ ctx = ctx_ ]( dpp::interaction_create_t const& e ) -> dpp::task< void > {
			auto const& event = static_cast< dpp::select_click_t const& >( e );
			ctx->selected = magic_enum::enum_cast< shop::ItemId >( event.values[ 0 ] );
			if ( not ctx->selected )
				co_return;

			ctx->params.clear();
			auto handler = shop::Handler::Get( *ctx->selected );

			auto msg = dpp::message{}.set_flags( dpp::m_ephemeral );
			for ( auto comp_type : handler->GetInputHandlers() )
			{
				auto& comp = ctx->components.at( comp_type );
				msg.add_component( comp->Root() );
			}

			auto& confirm = ctx->components.at( shop::InputType::Confirm );
			msg.add_component( confirm->Root() );

			co_await event.co_reply( msg );
		};

		auto drop_down = Dropdown( bot_ctx, options_cd );
		root_ = drop_down.Root();
	}

	std::map< shop::InputType, std::unique_ptr< Component > > Shop::MakeInputComponents( Context& bot_ctx )
	{
		auto self_id = ( std::uintptr_t )this;
		std::map< shop::InputType, std::unique_ptr< Component > > result{};

		auto user_component_cd = UserSelectData{};
		user_component_cd.id = std::format( "{}-shop-user", self_id );
		user_component_cd.placeholder = "Select a user to target:";
		user_component_cd.handler = [ ctx = ctx_ ]( dpp::interaction_create_t const& e ) -> dpp::task< void > {
			auto const& event = static_cast< dpp::select_click_t const& >( e );
			ctx->params[ "user" ] = dpp::snowflake( event.values[ 0 ] );
			co_await e.co_reply();
		};

		auto constexpr duration_values = std::array{ 1, 2, 5, 10, 15, 30, 60 };
		auto duration_options = duration_values | std::views::transform( []( auto opt ) { return dpp::select_option( std::format( "{} minute(s)", opt ), std::to_string( opt ) ); } ) | std::ranges::to< std::vector >();

		auto duration_component_cd = DropdownData{};
		duration_component_cd.id = std::format( "{}-shop-duration", self_id );
		duration_component_cd.placeholder = "Choose duration";
		duration_component_cd.options = std::move( duration_options );
		duration_component_cd.handler = [ ctx = ctx_ ]( dpp::interaction_create_t const& e ) -> dpp::task< void > {
			auto const& event = static_cast< dpp::select_click_t const& >( e );
			ctx->params[ "duration" ] = std::stoi( event.values[ 0 ] );
			co_await e.co_reply();
		};


		auto confirm_cd = ButtonData{};
		confirm_cd.id = std::format( "{}-shop-confirm", self_id );
		confirm_cd.label = "Confirm";
		confirm_cd.style = dpp::cos_success;
		confirm_cd.handler = [ ctx = ctx_, self_id, &bot_ctx ]( dpp::interaction_create_t const& e ) -> dpp::task< void > {
			co_await e.co_thinking( true );

			auto handler = shop::Handler::Get( *ctx->selected );
			co_await handler->HandlePurchase( e, ctx->params );

			auto self_id_str = std::to_string( self_id );
			std::erase_if( bot_ctx.component_handlers, [ & ]( auto const& kv ) { return kv.first.starts_with( self_id_str ); } );
			co_await e.co_follow_up( "" );
		};

		result[ shop::InputType::User ] = std::make_unique< UserSelect >( bot_ctx, user_component_cd );
		result[ shop::InputType::Duration ] = std::make_unique< Dropdown >( bot_ctx, duration_component_cd );
		result[ shop::InputType::Confirm ] = std::make_unique< Button >( bot_ctx, confirm_cd );

		return result;
	}
} // namespace iter8::view
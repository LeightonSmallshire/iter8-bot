#include "Shop.h"

#include "Component.h"

#include "Core/Image.h"
#include "Model/ShopItem.h"
#include "Model/Purchase.h"
#include "Utils/Shop.h"
#include "Logging/Log.h"

#include <stb_image_write.h>

#include <regex>

namespace iter8::view
{
	static void SearchComponentsAndUpdate( std::vector< dpp::component >& comps, std::string match_id, std::function< void( dpp::component& ) > const& on_update )
	{
		for ( auto& c : comps )
		{
			if ( c.custom_id == match_id )
			{
				on_update( c );
				return;
			}

			SearchComponentsAndUpdate( c.components, match_id, on_update );
		}
	}

	Shop::Shop( Context& bot_ctx )
		: ctx_{ std::make_shared< ShopContext >() }
	{
		auto self_id = ( std::uintptr_t )this;

		ctx_->components = MakeInputComponents( bot_ctx );

		auto select_options = std::vector< dpp::select_option >{};

		auto&& [ is_sale, end_date ] = shop::IsOngoingSale( bot_ctx.db );
		float discount = is_sale ? 0.5f : 1.0f;

		auto embed = dpp::embed{};
		embed.set_title( "🛒 Clockwork Shop 🛒" );
		embed.set_color( dpp::colors::summer_sky );

		auto items = bot_ctx.db.Select< ShopItem >().ReadAll();
		std::ranges::sort( items, std::less{}, []( auto const& i ) { return std::to_underlying( i.category ); } );

		auto groups = items | std::views::chunk_by( []( auto const& a, auto const& b ) { return a.category == b.category; } ) | std::ranges::to< std::vector >();

		for ( auto&& [ idx, group ] : std::views::enumerate( groups ) )
		{
			auto category = group[ 0 ].category;
			embed.add_field( std::format( "{}", category ), "────────────────────────────────────────────────────────" );

			for ( auto const& item : group )
			{
				using clock = std::chrono::system_clock;
				float cost = item.id != db::ToId( shop::ItemId::BlackFridaySale ) ? item.cost * discount : item.cost;
				auto tp = clock::time_point{} + std::chrono::duration_cast< std::chrono::seconds >( std::chrono::duration< float >( cost ) );
				embed.add_field( item.description, std::format( "{:%T}", std::chrono::round< std::chrono::seconds >( tp ) ) );

				auto& option = select_options.emplace_back();
				option.label = magic_enum::enum_name( static_cast< shop::ItemId >( std::to_underlying( item.id ) ) );
				option.description = item.description;
				option.value = option.label;
			}

			if ( idx < groups.size() - 1 )
				embed.add_field( "", "\u200b" );
		}

		if ( is_sale )
			embed.set_footer( std::format( "Sale ends at {:%T}", *end_date ), {} );

		ComponentData options_cd{};
		options_cd.id = std::format( "{}-shop-select", ( uintptr_t )this );
		options_cd.type = dpp::cot_selectmenu;
		options_cd.placeholder = "Choose an item...";
		options_cd.options = std::move( select_options );
		options_cd.handler = [ ctx = ctx_, &bot_ctx, self_id ]( dpp::interaction_create_t const& e ) -> dpp::task< void > {
			auto const& event = static_cast< dpp::select_click_t const& >( e );
			ctx->selected = magic_enum::enum_cast< shop::ItemId >( event.values[ 0 ] );
			if ( not ctx->selected )
				co_return;

			co_await event.co_reply();

			ctx->params.clear();
			auto handler = shop::Handler::Get( *ctx->selected );

			auto msg = dpp::message{}.set_flags( dpp::m_ephemeral );

			for ( auto comp_type : handler->GetInputHandlers() )
			{
				auto comp = ctx->components.at( comp_type );
				auto row = dpp::component{};
				row.add_component( comp );
				msg.add_component( row );
			}

			auto confirm = ctx->components.at( shop::InputType::Confirm );
			confirm.label = std::format( "Buy - {}", *ctx->selected );

			auto cancel = ctx->components.at( shop::InputType::Cancel );

			auto confirm_row = dpp::component{};
			confirm_row.add_component( confirm );
			confirm_row.add_component( cancel );
			msg.add_component( confirm_row );

			auto result = co_await event.co_edit_original_response( msg );
			if ( result.is_error() )
				log::Error( "Follow-up failed: {}", result.get_error().message );
		};

		ctx_->message.add_embed( embed );
		ctx_->message.add_component( dpp::component{}.add_component( MakeComponent( bot_ctx, options_cd ) ) );

		// Cleanup handlers after fifteen minutes
		dpp::oneshot_timer t{
			&bot_ctx.bot,
			60 * 15,
			[ self_id, &bot_ctx ]( dpp::timer ) {
				auto self_id_str = std::to_string( self_id );
				std::erase_if( bot_ctx.component_handlers, [ & ]( auto const& kv ) { return kv.first.starts_with( self_id_str ); } );
			}
		};
	}

	std::map< shop::InputType, dpp::component > Shop::MakeInputComponents( Context& bot_ctx )
	{
		auto const self_id = ( std::uintptr_t )this;

		auto const user_id = std::format( "{}-shop-user", self_id );
		auto const duration_id = std::format( "{}-shop-duration", self_id );
		auto const colour_id = std::format( "{}-shop-colour", self_id );
		auto const nickname_id = std::format( "{}-shop-nickname", self_id );
		auto const confirm_id = std::format( "{}-shop-confirm", self_id );

		std::map< shop::InputType, dpp::component > result{};

		auto user_component_cd = ComponentData{};
		user_component_cd.id = user_id;
		user_component_cd.type = dpp::cot_user_selectmenu;
		user_component_cd.placeholder = "Select a user to target:";
		user_component_cd.handler = [ =, ctx = ctx_ ]( dpp::interaction_create_t const& e ) -> dpp::task< void > {
			auto const& event = static_cast< dpp::select_click_t const& >( e );
			ctx->params[ "user" ] = dpp::snowflake( event.values[ 0 ] );

			co_await e.co_reply();

			auto handler = shop::Handler::Get( *ctx->selected );
			if ( handler->HasAllParameters( ctx->params ) )
			{
				auto msg = e.command.msg;
				SearchComponentsAndUpdate( msg.components, confirm_id, []( auto& c ) {
					c.disabled = false;
				} );

				// For some reason need to re-populate the duration field as the component does not hold the updated value
				SearchComponentsAndUpdate( msg.components, duration_id, [ & ]( auto& c ) {
					c.value = std::to_string( std::any_cast< int >( ctx->params[ "duration" ] ) );
				} );

				co_await e.co_edit_original_response( msg );
			}
		};

		auto constexpr duration_values = std::array{ 1, 2, 5, 10, 15, 30, 60 };
		auto duration_options = duration_values | std::views::transform( []( auto opt ) { return dpp::select_option( std::format( "{} minute(s)", opt ), std::to_string( opt ) ); } ) | std::ranges::to< std::vector >();

		auto duration_component_cd = ComponentData{};
		duration_component_cd.id = duration_id;
		duration_component_cd.type = dpp::cot_selectmenu;
		duration_component_cd.placeholder = "Choose duration";
		duration_component_cd.options = std::move( duration_options );
		duration_component_cd.handler = [ =, ctx = ctx_ ]( dpp::interaction_create_t const& e ) -> dpp::task< void > {
			auto const& event = static_cast< dpp::select_click_t const& >( e );
			ctx->params[ "duration" ] = std::stoi( event.values[ 0 ] );

			co_await e.co_reply();

			auto handler = shop::Handler::Get( *ctx->selected );
			if ( handler->HasAllParameters( ctx->params ) )
			{
				auto msg = e.command.msg;
				SearchComponentsAndUpdate( msg.components, confirm_id, []( auto& c ) {
					c.disabled = false;
				} );

				// For some reason need to re-populate the duration field as the component does not hold the updated value
				SearchComponentsAndUpdate( msg.components, duration_id, [ & ]( auto& c ) {
					c.value = std::to_string( std::any_cast< int >( ctx->params[ "duration" ] ) );
				} );

				co_await e.co_edit_original_response( msg );
			}
		};


		auto colour_input_cd = ComponentData{};
		colour_input_cd.id = colour_id;
		colour_input_cd.type = dpp::cot_button;
		colour_input_cd.label = "Enter colour";
		colour_input_cd.style = dpp::cos_primary;
		colour_input_cd.handler = [ =, ctx = ctx_, &bot_ctx, ]( dpp::interaction_create_t const& e ) -> dpp::task< void > {
			ModalData modal_cd{};
			modal_cd.id = std::format( "{}-shop-colour-modal", self_id );
			modal_cd.title = "Enter a colour hex colour code";

			ComponentData text_cd{};
			text_cd.id = std::format( "{}-shop-colour-modal-field", self_id );
			text_cd.type = dpp::cot_text;
			text_cd.text_style = dpp::text_short;
			text_cd.label = "HEX code";
			text_cd.placeholder = "#ff8800";

			modal_cd.components.push_back( MakeComponent( bot_ctx, text_cd ) );

			modal_cd.handler = [ =, &bot_ctx ]( dpp::interaction_create_t const& e ) -> dpp::task< void > {
				auto const& event = static_cast< dpp::form_submit_t const& >( e );
				auto hex_code = std::get< std::string >( event.components[ 0 ].value );

				static std::regex const hex_regex( R"(^(#[0-9A-Fa-f]{6})$)" );
				if ( not std::regex_match( hex_code, hex_regex ) )
				{
					auto msg = dpp::message( "❌ That isn't a valid colour code" ).set_flags( dpp::m_ephemeral );
					co_await e.co_reply( msg );
					co_return;
				}

				co_await e.co_reply();

				auto colour_str = hex_code.substr( 1 ) + "ff"; // Add alpha
				auto colour = std::stoul( colour_str, nullptr, 16 );
				ctx->params[ "colour" ] = static_cast< std::uint32_t >( colour );

				auto image_data = MakeImageData( colour );

				dpp::emoji new_emoji{};
				new_emoji.name = e.command.usr.username;
				new_emoji.image_data = dpp::utility::image_data( dpp::image_type::i_png, image_data.data(), image_data.size() );
				auto result = co_await bot_ctx.bot.co_guild_emoji_create( e.command.guild_id, new_emoji );
				auto actual_emoji = std::get< dpp::emoji >( result.value );

				auto handler = shop::Handler::Get( *ctx->selected );

				auto msg = e.command.msg;
				auto update_emoji = dpp::component_emoji{
					.name = actual_emoji.name,
					.id = actual_emoji.id
				};

				SearchComponentsAndUpdate( msg.components, colour_id, [ & ]( auto& c ) {
					c.label = hex_code;
					c.emoji = update_emoji;
				} );

				if ( handler->HasAllParameters( ctx->params ) )
				{
					SearchComponentsAndUpdate( msg.components, confirm_id, []( auto& c ) {
						c.disabled = false;
					} );
				}

				co_await e.co_edit_original_response( msg );

				co_await bot_ctx.bot.co_guild_emoji_delete( e.command.guild_id, actual_emoji.id );
			};

			auto modal = MakeModal( bot_ctx, modal_cd );
			auto confirm = co_await e.co_dialog( modal );
			if ( confirm.is_error() )
				log::Error( "Follow-up failed: {}", confirm.get_error().message );
		};


		auto nickname_input_cd = ComponentData{};
		nickname_input_cd.id = nickname_id;
		nickname_input_cd.type = dpp::cot_button;
		nickname_input_cd.label = "Enter nickname";
		nickname_input_cd.style = dpp::cos_primary;
		nickname_input_cd.handler = [ =, ctx = ctx_, &bot_ctx ]( dpp::interaction_create_t const& e ) -> dpp::task< void > {
			ModalData modal_cd{};
			modal_cd.id = std::format( "{}-shop-nickanme-modal", self_id );
			modal_cd.title = "Enter a new nickname";

			ComponentData text_cd{};
			text_cd.id = std::format( "{}-shop-nickanme-modal-field", self_id );
			text_cd.type = dpp::cot_text;
			text_cd.text_style = dpp::text_short;
			text_cd.label = "Nickname";
			text_cd.placeholder = ( co_await GetMember( bot_ctx.bot, e.command.usr.id ) ).get_nickname();

			modal_cd.components.push_back( MakeComponent( bot_ctx, text_cd ) );

			modal_cd.handler = [ ctx, &bot_ctx, self_id, nickname_id ]( dpp::interaction_create_t const& e ) -> dpp::task< void > {
				auto const& event = static_cast< dpp::form_submit_t const& >( e );
				auto nickname = std::get< std::string >( event.components[ 0 ].value );

				co_await e.co_reply();

				ctx->params[ "text" ] = nickname;

				auto handler = shop::Handler::Get( *ctx->selected );

				auto msg = e.command.msg;

				SearchComponentsAndUpdate( msg.components, nickname_id, [ & ]( auto& c ) {
					c.label = nickname;
				} );

				if ( handler->HasAllParameters( ctx->params ) )
				{
					SearchComponentsAndUpdate( msg.components, confirm_id, []( auto& c ) {
						c.disabled = false;
					} );
				}

				co_await e.co_edit_original_response( msg );
			};

			auto modal = MakeModal( bot_ctx, modal_cd );
			auto confirm = co_await e.co_dialog( modal );
			if ( confirm.is_error() )
				log::Error( "Follow-up failed: {}", confirm.get_error().message );
		};


		auto confirm_cd = ComponentData{};
		confirm_cd.id = confirm_id;
		confirm_cd.type = dpp::cot_button;
		confirm_cd.style = dpp::cos_success;
		confirm_cd.disabled = true;
		confirm_cd.handler = [ -, ctx = ctx_, &bot_ctx ]( dpp::interaction_create_t const& e ) -> dpp::task< void > {
			co_await e.co_reply();

			auto handler = shop::Handler::Get( *ctx->selected );

			if ( not handler->HasAllParameters( ctx->params ) )
			{
				auto msg = e.command.msg;
				msg.content = "❌ Please provide all parameters.";
				co_await e.co_edit_original_response( msg );
				co_return;
			}

			auto item = bot_ctx.db.SelectOne< ShopItem >( db::Where( db::WhereParam( &ShopItem::id, db::ToId( *ctx->selected ) ) ) );

			auto&& [ is_sale, end_date ] = shop::IsOngoingSale( bot_ctx.db );
			float discount = is_sale ? 0.5f : 1.0f;

			int count = ctx->params.contains( "duration" ) ? std::any_cast< int >( ctx->params.at( "duration" ) ) : 1;

			float cost = item->cost * discount * count;
			auto tp = TimePoint( std::chrono::duration_cast< std::chrono::system_clock::duration >( std::chrono::duration< double >( cost ) ) );

			auto msg = dpp::message( std::format( "This purchase will cost you {:%T}", std::chrono::round< std::chrono::seconds >( tp ) ) );

			auto confirm = ctx->components.at( shop::InputType::Purchase );
			auto cancel = ctx->components.at( shop::InputType::Cancel );

			auto confirm_row = dpp::component{};
			confirm_row.add_component( confirm );
			confirm_row.add_component( cancel );
			msg.add_component( confirm_row );

			co_await e.co_edit_original_response( msg );
		};


		auto purchase_cd = ComponentData{};
		purchase_cd.id = std::format( "{}-shop-purchase", self_id );
		purchase_cd.label = "Purchase";
		purchase_cd.type = dpp::cot_button;
		purchase_cd.style = dpp::cos_success;
		purchase_cd.handler = [ ctx = ctx_, self_id, &bot_ctx ]( dpp::interaction_create_t const& e ) -> dpp::task< void > {
			co_await e.co_reply();

			auto item = bot_ctx.db.SelectOne< ShopItem >( db::Where( db::WhereParam( &ShopItem::id, db::ToId( *ctx->selected ) ) ) );

			auto&& [ is_sale, end_date ] = shop::IsOngoingSale( bot_ctx.db );
			float discount = is_sale ? 0.5f : 1.0f;

			int count = ctx->params.contains( "duration" ) ? std::any_cast< int >( ctx->params.at( "duration" ) ) : 1;

			float cost = item->cost * discount * count;

			if ( shop::CanAffordPurchase( bot_ctx.db, e.command.usr.id, cost ) )
			{
				auto purchase = Purchase{
					.user_id = db::ToId( e.command.usr.id ),
					.item_id = item->id,
					.timestamp = std::chrono::system_clock::now(),
					.cost = cost
				};

				auto handler = shop::Handler::Get( *ctx->selected );
				co_await handler->HandlePurchase( e, ctx->params );

				bot_ctx.db.Insert( purchase );

				auto user = bot_ctx.db.SelectOne< User >( db::Where( db::WhereParam( &User::id, db::ToId( e.command.usr.id ) ) ) ).value();
				user.credit -= cost;
				bot_ctx.db.Update( user );

				auto self_id_str = std::to_string( self_id );
				std::erase_if( bot_ctx.component_handlers, [ & ]( auto const& kv ) { return kv.first.starts_with( self_id_str ); } );

				co_await e.co_edit_original_response( std::format( "✅ Purchased **{}**.", item->description ) );
			}
			else
			{
				co_await e.co_edit_original_response( "❌ You can't afford this purchase." );
			}
		};

		auto cancel_cd = ComponentData{};
		cancel_cd.id = std::format( "{}-shop-cancel", self_id );
		cancel_cd.label = "Cancel";
		cancel_cd.type = dpp::cot_button;
		cancel_cd.style = dpp::cos_primary;
		cancel_cd.handler = [ ctx = ctx_, self_id, &bot_ctx ]( dpp::interaction_create_t const& e ) -> dpp::task< void > {
			co_await e.co_reply();
			ctx->selected = {};
			ctx->params.clear();
			auto confirm = co_await e.co_edit_original_response( ctx->message );
		};

		result[ shop::InputType::User ] = MakeComponent( bot_ctx, user_component_cd );
		result[ shop::InputType::Duration ] = MakeComponent( bot_ctx, duration_component_cd );
		result[ shop::InputType::Colour ] = MakeComponent( bot_ctx, colour_input_cd );
		result[ shop::InputType::Text ] = MakeComponent( bot_ctx, nickname_input_cd );

		result[ shop::InputType::Confirm ] = MakeComponent( bot_ctx, confirm_cd );
		result[ shop::InputType::Purchase ] = MakeComponent( bot_ctx, purchase_cd );
		result[ shop::InputType::Cancel ] = MakeComponent( bot_ctx, cancel_cd );

		return result;
	}
} // namespace iter8::view
#include "ShopCog.h"

#include "Model/User.h"
#include "Utils/Shop.h"
#include "Shop/Item.h"
#include "View/Shop.h"
#include "Logging/Log.h"

namespace iter8
{
	ShopCog::ShopCog( Context& ctx )
		: Cog( ctx )
	{
		AddCommand( { "shop", "Let's see what the lovely shop has to offer" }, std::bind_front( &ShopCog::OnShopCommand, this ) );
		AddCommand( { "credit", "Find out how much shop credit everyone has" }, std::bind_front( &ShopCog::OnCreditCommand, this ) );
	}

	dpp::task< void > ShopCog::OnShopCommand( dpp::slashcommand_t const& event )
	{
		co_await event.co_thinking( true );

		view::Shop shop( ctx_ );

		auto confirm = co_await event.co_follow_up( shop.Message() );
		if ( confirm.is_error() )
			log::Error( "Follow-up failed: {}", confirm.get_error().message );
	}

	dpp::task< void > ShopCog::OnCreditCommand( dpp::slashcommand_t const& event )
	{
		co_await event.co_thinking( true );

		auto members = co_await GetNonBotMembers( ctx_.bot, event.command.guild_id );
		auto credit = members | std::views::transform( [ & ]( auto const& mem ) { return shop::GetCredit( ctx_.db, mem.user_id ); } );

		auto entries = std::views::zip( members, credit ) | std::ranges::to< std::vector >();
		std::ranges::sort( entries, std::greater{}, []( auto&& entry ) { return std::get< 1 >( entry ); } );

		auto embed = dpp::embed{};
		embed.set_title( "💵 How much is everyone worth? 💵" );
		embed.set_color( dpp::colors::summer_sky );

		for ( auto&& [ user, value ] : entries )
		{
			using clock = std::chrono::system_clock;
			auto tp = clock::time_point{} + std::chrono::duration_cast< std::chrono::seconds >( std::chrono::duration< float >( value ) );
			embed.add_field( user.get_nickname(), std::format( "{:%T}", std::chrono::round< std::chrono::seconds >( tp ) ) );
		}

		dpp::message msg( embed );
		co_await event.co_follow_up( msg );
	}
} // namespace iter8
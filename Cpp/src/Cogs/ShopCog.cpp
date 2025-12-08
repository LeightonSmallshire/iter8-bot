#include "ShopCog.h"

#include "Model/User.h"
#include "Utils/Shop.h"
#include "Shop/Item.h"

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
		co_await event.co_thinking();

		auto&& [ is_sale, end_date ] = shop::IsOngoingSale( ctx_.db );
		float discount = is_sale ? 0.5f : 1.0f;

		auto embed = dpp::embed{};
		embed.set_title( "🛒 Clockwork Shop 🛒" );
		embed.set_color( 0xFF0000FF );

		auto items = ctx_.db.Select< ShopItem >().ReadAll();
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
			}

			if ( idx < groups.size() - 1 )
				embed.add_field( "", "\u200b" );
		}

		if ( is_sale )
			embed.set_footer( std::format( "Sale ends at {:%T}", *end_date ), {} );

		dpp::message msg( embed );
		co_await event.co_follow_up( msg );
	}

	dpp::task< void > ShopCog::OnCreditCommand( dpp::slashcommand_t const& event )
	{
		co_await event.co_thinking();

		auto guild = co_await GetGuild( ctx_.bot, event.command.guild_id );

		auto member_filter = []( dpp::guild_member const& member ) {
			auto user = member.get_user();
			return not member.is_guild_owner() and user and not user->is_bot();
		};
		auto members = guild.members | std::views::values | std::views::filter( member_filter );
		auto credit = members | std::views::transform( [ & ]( auto const& mem ) { return shop::GetCredit( ctx_.db, mem.user_id ); } );

		auto entries = std::views::zip( members, credit ) | std::ranges::to< std::vector >();
		std::ranges::sort( entries, std::greater{}, []( auto&& entry ) { return std::get< 1 >( entry ); } );

		auto embed = dpp::embed{};
		embed.set_title( "💵 How much is everyone worth? 💵" );
		embed.set_color( 0xFF0000FF );

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
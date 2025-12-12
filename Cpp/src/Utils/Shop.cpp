#include "Shop.h"

#include "Model/User.h"
#include "Model/Purchase.h"
#include "Shop/Item.h"

namespace iter8::shop
{
	static float Sum( std::ranges::input_range auto&& range, auto&& projection = std::identity{} )
	{
		return std::ranges::fold_left( range | std::views::transform( projection ), 0.0, std::plus{} );
	}

	float GetCredit( db::Connection& db, dpp::snowflake user_id )
	{
		auto user = db.SelectOne< User >( db::Where( db::WhereParam( &User::id, db::ToId( user_id ) ) ) );
		if ( not user )
			return 0;

		return user->credit;
	}

	bool CanAffordPurchase( db::Connection& db, dpp::snowflake user_id, float cost )
	{
		return GetCredit( db, user_id ) >= cost;
	}

	std::tuple< bool, std::optional< TimePoint > > IsOngoingSale( db::Connection& db )
	{
		auto const sale_id = db::ForeignKey< ShopItem >{ db::ToId( shop::ItemId::BlackFridaySale ) };
		auto sale = db.SelectOne< Purchase >( 
			db::Where( db::WhereParam( &Purchase::item_id, sale_id ) ), 
			db::OrderBy( db::OrderParam( &Purchase::timestamp, db::Ordering::Desc ) )
		);

		if ( not sale )
			return { false, std::nullopt };

		auto end_time = sale->timestamp + std::chrono::minutes( 30 );
		return { std::chrono::system_clock::now() < end_time, end_time };
	}
} // namespace iter8::shop
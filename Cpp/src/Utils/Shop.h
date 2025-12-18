#pragma once

#include "Database/Connection.h"

#include "Model/ShopItem.h"

namespace iter8::shop
{
	float GetCredit( db::Connection& db, dpp::snowflake user_id );

	bool CanAffordPurchase( db::Connection& db, dpp::snowflake user_id, float cost );
	std::tuple< bool, std::optional< TimePoint > > IsOngoingSale( db::Connection& db );
}
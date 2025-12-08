#include "Item.h"

#include "Items/AdminTimeout.h"

namespace iter8::shop
{
	static std::map< ItemId, std::shared_ptr< ItemHandler > > const s_ItemHandlers = {
		{ ItemId::AdminTimeout, std::make_shared< AdminTimeout >() }
	};

	std::shared_ptr< ItemHandler > GetShopHandler( db::ID item_id )
	{
		auto id = static_cast< ItemId >( item_id );
		if ( not s_ItemHandlers.contains( id ) )
			return nullptr;

		return s_ItemHandlers.at( id );
	}
} // namespace iter8::shop
#include "Item.h"

#include "Items/AdminReroll.h"
#include "Items/AdminTicket.h"
#include "Items/AdminTimeout.h"
#include "Items/BlackFridaySale.h"
#include "Items/BullyReroll.h"
#include "Items/BullyTarget.h"
#include "Items/BullyTimeout.h"
#include "Items/ChooseColourOther.h"
#include "Items/ChooseColourSelf.h"
#include "Items/ChooseNicknameOther.h"
#include "Items/ChooseNicknameSelf.h"
#include "Items/MakeAdmin.h"
#include "Items/RandomTimeout.h"
#include "Items/UserTimeout.h"

namespace iter8::shop
{
	void Handler::Init( db::Connection& db )
	{
		s_ItemHandlers[ ItemId::AdminReroll ] = std::make_shared< AdminReroll >( db );
		s_ItemHandlers[ ItemId::AdminTicket ] = std::make_shared< AdminTicket >( db );
		s_ItemHandlers[ ItemId::AdminTimeout ] = std::make_shared< AdminTimeout >( db );
		s_ItemHandlers[ ItemId::BlackFridaySale ] = std::make_shared< BlackFridaySale >( db );
		s_ItemHandlers[ ItemId::BullyReroll ] = std::make_shared< BullyReroll >( db );
		s_ItemHandlers[ ItemId::BullyChoose ] = std::make_shared< BullyTarget >( db );
		s_ItemHandlers[ ItemId::BullyTimeout ] = std::make_shared< BullyTimeout >( db );
		s_ItemHandlers[ ItemId::ChooseColourOther ] = std::make_shared< ChooseColourOther >( db );
		s_ItemHandlers[ ItemId::ChooseColourSelf ] = std::make_shared< ChooseColourSelf >( db );
		s_ItemHandlers[ ItemId::ChooseNicknameOther ] = std::make_shared< ChooseNicknameOther >( db );
		s_ItemHandlers[ ItemId::ChooseNicknameSelf ] = std::make_shared< ChooseNicknameSelf >( db );
		s_ItemHandlers[ ItemId::MakeAdmin ] = std::make_shared< MakeAdmin >( db );
		s_ItemHandlers[ ItemId::RandomTimeout ] = std::make_shared< RandomTimeout >( db );
		s_ItemHandlers[ ItemId::UserTimeout ] = std::make_shared< UserTimeout >( db );
	}

	std::shared_ptr< Handler > Handler::Get( db::ID item_id )
	{
		auto id = static_cast< ItemId >( item_id );
		auto it = s_ItemHandlers.find( id );
		if ( it == s_ItemHandlers.end() )
			return nullptr;

		return it->second;
	}
} // namespace iter8::shop
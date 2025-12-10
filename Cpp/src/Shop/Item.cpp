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
	void Handler::Init( Context& ctx )
	{
		s_ItemHandlers[ ItemId::AdminReroll ] = std::make_shared< AdminReroll >( ctx );
		s_ItemHandlers[ ItemId::AdminTicket ] = std::make_shared< AdminTicket >( ctx );
		s_ItemHandlers[ ItemId::AdminTimeout ] = std::make_shared< AdminTimeout >( ctx );
		s_ItemHandlers[ ItemId::BlackFridaySale ] = std::make_shared< BlackFridaySale >( ctx );
		s_ItemHandlers[ ItemId::BullyReroll ] = std::make_shared< BullyReroll >( ctx );
		s_ItemHandlers[ ItemId::BullyChoose ] = std::make_shared< BullyTarget >( ctx );
		s_ItemHandlers[ ItemId::BullyTimeout ] = std::make_shared< BullyTimeout >( ctx );
		s_ItemHandlers[ ItemId::ChooseColourOther ] = std::make_shared< ChooseColourOther >( ctx );
		s_ItemHandlers[ ItemId::ChooseColourSelf ] = std::make_shared< ChooseColourSelf >( ctx );
		s_ItemHandlers[ ItemId::ChooseNicknameOther ] = std::make_shared< ChooseNicknameOther >( ctx );
		s_ItemHandlers[ ItemId::ChooseNicknameSelf ] = std::make_shared< ChooseNicknameSelf >( ctx );
		s_ItemHandlers[ ItemId::MakeAdmin ] = std::make_shared< MakeAdmin >( ctx );
		s_ItemHandlers[ ItemId::RandomTimeout ] = std::make_shared< RandomTimeout >( ctx );
		s_ItemHandlers[ ItemId::UserTimeout ] = std::make_shared< UserTimeout >( ctx );
	}

	std::shared_ptr< Handler > Handler::Get( ItemId item_id )
	{
		auto it = s_ItemHandlers.find( item_id );
		if ( it == s_ItemHandlers.end() )
			return nullptr;

		return it->second;
	}
} // namespace iter8::shop
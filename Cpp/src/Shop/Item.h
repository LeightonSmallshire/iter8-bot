#pragma once

#include "Database/Connection.h"

#include "dpp/dpp.h"

namespace iter8::shop
{
	enum class ItemId : std::uint64_t
	{
		AdminTimeout = 1,
		UserTimeout = 2,
		BullyTimeout = 5,
		RandomTimeout = 14,
		BullyReroll = 3,
		BullyChoose = 4,
		AdminTicket = 7,
		AdminReroll = 8,
		MakeAdmin = 6,
		ChooseNicknameSelf = 9,
		ChooseNicknameOther = 10,
		ChooseColourSelf = 11,
		ChooseColourOther = 12,
		BlackFridaySale = 13
	};

	class Handler
	{
	public:
		Handler( db::Connection& db )
			: db_{ db }
		{}

		virtual ~Handler() = default;
		virtual dpp::task< void > HandlePurchase( dpp::interaction_create_t& event, std::map< std::string, std::any > const& params ) = 0;
		virtual std::vector< dpp::component > GetInputHandlers()
		{
			return {};
		}

		static void Init( db::Connection& db );
		static std::shared_ptr< Handler > Get( db::ID item_id );

	protected:
		db::Connection& db_;

	private:
		inline static std::map< ItemId, std::shared_ptr< Handler > > s_ItemHandlers{};
	};
}
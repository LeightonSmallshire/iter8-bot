#pragma once

#include "Context.h"

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

	enum class InputType
	{
		User,
		Duration,
		Colour,
		Text,

		// Dont need to specify these, added automatically on selection
		Confirm,
		Cancel,
		Purchase,
	};

	class Handler
	{
	public:
		Handler( Context& ctx )
			: ctx_{ ctx }
		{}

		virtual ~Handler() = default;

		virtual dpp::task< void > HandlePurchase( dpp::interaction_create_t const& event, std::map< std::string, std::any > const& params ) = 0;
		virtual std::vector< InputType > GetInputHandlers()
		{
			return {};
		}

		bool HasAllParameters(std::map< std::string, std::any > const& params)
		{
			auto param_types = GetInputHandlers();

			if ( param_types.size() != params.size() )
				return false;
			
			auto param_exists = [ & ]( auto type ) {
				auto type_str = ToLower( magic_enum::enum_name( type ) );
				return params.contains( type_str );
			};

			return std::ranges::all_of( param_types, param_exists );
		}

		static void Init( Context& ctx );
		static std::shared_ptr< Handler > Get( ItemId item_id );

	protected:
		Context& ctx_;

	private:
		inline static std::map< ItemId, std::shared_ptr< Handler > > s_ItemHandlers{};
	};
}
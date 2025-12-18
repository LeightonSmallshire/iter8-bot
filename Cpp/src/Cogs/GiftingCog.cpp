#include "GiftingCog.h"

#include "Model/Gift.h"
#include "Utils/Shop.h"

namespace iter8
{
	static std::map< std::string, float > const s_GiftEmojiValues = {
		{ "🥇", 600.f },
		{ "🥈", 300.f },
		{ "🥉", 60.f },
	};

	GiftingCog::GiftingCog( Context& ctx )
		: Cog( ctx )
	{
		AddListener( ctx.bot.on_message_reaction_add, std::bind_front( &GiftingCog::OnReactionAdded, this ) );
		AddListener( ctx.bot.on_message_reaction_remove, std::bind_front( &GiftingCog::OnReactionRemoved, this ) );
	}

	dpp::task< void > GiftingCog::OnReactionAdded( dpp::message_reaction_add_t const& e )
	{
		if ( not s_GiftEmojiValues.contains( e.reacting_emoji.name ) )
			co_return;

		if ( e.reacting_user.id == e.message_author_id )
			co_return;

		auto author_member = co_await GetMember( ctx_.bot, e.message_author_id );
		auto author_user = co_await GetUser( ctx_.bot, e.message_author_id );

		if ( author_user.is_bot() or author_member.is_guild_owner() )
			co_return;

		auto const value = s_GiftEmojiValues.at( e.reacting_emoji.name );

		if ( not shop::CanAffordPurchase( ctx_.db, e.reacting_user.id, value ) )
			co_return;

		auto gifter = ctx_.db.SelectOne< User >( db::Where( db::Param( &User::id, db::ToId( e.reacting_user.id ) ) ) ).value();
		auto recipient = ctx_.db.SelectOne< User >( db::Where( db::Param( &User::id, db::ToId( e.message_author_id ) ) ) ).value();

		gifter.credit -= value;
		recipient.credit += value;

		ctx_.db.Update( gifter );
		ctx_.db.Update( recipient );

		auto gift = Gift{
			.value = value,
			.gifter_id = gifter.id,
			.recipient_id = recipient.id
		};

		ctx_.db.Insert( gift );

		auto tp = TimePoint( std::chrono::duration_cast< std::chrono::system_clock::duration >( std::chrono::duration< double >( value ) ) );
		auto msg = dpp::message{ e.channel_id, std::format( "<@{}> gifted <@{}> {:%T} for this message.", e.reacting_user.id.str(), e.message_author_id.str(), std::chrono::round< std::chrono::seconds >( tp ) ) };
		co_await ctx_.bot.co_message_create( msg );
	}

	dpp::task< void > GiftingCog::OnReactionRemoved( dpp::message_reaction_remove_t const& e )
	{
		if ( not s_GiftEmojiValues.contains( e.reacting_emoji.name ) )
			co_return;

		auto result = co_await ctx_.bot.co_message_get( e.message_id, e.channel_id );
		auto msg = std::get< dpp::message >( result.value );

		if ( e.reacting_user_id == msg.author.id )
			co_return;

		auto const value = s_GiftEmojiValues.at( e.reacting_emoji.name );

		auto where = db::Where(
			db::Param( &Gift::gifter_id, db::ToId( e.reacting_user_id ) ),
			db::Param( &Gift::recipient_id, db::ToId( msg.author.id ) ),
			db::Param( &Gift::value, value ) );

		auto join = db::On(
			db::Param( &Gift::gifter_id, db::JoinType::Inner ),
			db::Param( &Gift::recipient_id, db::JoinType::Inner ) );

		auto did_gift = ctx_.db.JoinSelectOne< Gift, User, User >( join, where );

		if ( not did_gift )
			co_return;

		auto&& [ gift, gifter, recipient ] = *did_gift;

		gifter.credit += value;
		recipient.credit -= value;

		ctx_.db.Update( gifter );
		ctx_.db.Update( recipient );

		ctx_.db.Delete< Gift >( db::Where( db::Param( &Gift::id, gift.id ) ) );

		auto response = dpp::message{ e.channel_id, std::format( "<@{}> took away their gift <@{}> for this message.", e.reacting_user_id.str(), msg.author.id.str() ) };
		co_await ctx_.bot.co_message_create( response );

	}

} // namespace iter8
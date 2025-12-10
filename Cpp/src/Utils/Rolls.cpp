#include "Rolls.h"

#include "Core/Discord.h"
#include "Core/Random.h"

namespace iter8::roll
{
	static std::string MakeEmojiNumber( int i )
	{
		return std::format( ":number_{}:", i );
	}

	dpp::task< dpp::snowflake > DoRoleRoll(
		dpp::interaction_create_t const& event,
		dpp::snowflake role_id,
		std::vector< dpp::guild_member > const& table,
		std::string_view title,
		std::pair< std::format_string< std::string, std::string >, std::format_string< std::string > > response )
	{
		constexpr auto ROLL_GIF_URL = "https://media.tenor.com/XYkAxffY_PsAAAAM/dice-bae-dice.gif";

		if ( not event.owner )
			co_return 0;

		auto& bot = *event.owner;

		auto role = co_await GetRole( bot, event.command.guild_id, role_id );
		auto const& members = role.get_members();

		auto prev_user = members.empty() ? std::optional< dpp::snowflake >{} : members.begin()->first;

		auto table_embed = dpp::embed{};
		table_embed.set_title( title );
		table_embed.set_color( dpp::colors::yellow_orange );

		for ( auto&& [ idx, user ] : std::views::enumerate( table ) )
		{
			table_embed.add_field( MakeEmojiNumber( idx + 1 ), user.get_mention() );
		}

		auto table_msg = dpp::message{ "@everyone" };
		table_msg.add_embed( table_embed );

		co_await event.co_follow_up( table_msg );

		if ( table.empty() )
		{
			co_await event.co_follow_up( "There are no users for this roll." );
			co_return 0;
		}

		co_await bot.co_sleep( 5 );

		auto roll_embed = dpp::embed{};
		roll_embed.title = "Rolling...";
		roll_embed.set_image( ROLL_GIF_URL );

		auto roll_msg = dpp::message( roll_embed );
		co_await event.co_edit_response( roll_msg );

		co_await bot.co_sleep( 4 );

		auto index = Random( table.size() );

		co_await event.co_edit_response( std::format( "A  {} was rolled!", MakeEmojiNumber( index + 1 ) ) );

		co_await bot.co_sleep( 3 );

		auto new_user = table[ index ];

		if ( prev_user )
			co_await bot.co_guild_member_remove_role( event.command.guild_id, *prev_user, role_id );

		co_await bot.co_guild_member_add_role( event.command.guild_id, new_user.user_id, role_id );

		if ( prev_user )
			co_await event.co_edit_response( std::format( response.first, prev_user->str(), new_user.user_id.str() ) );
		else
			co_await event.co_edit_response( std::format( response.second, new_user.user_id.str() ) );

		co_return new_user.user_id;
	}
} // namespace iter8::roll